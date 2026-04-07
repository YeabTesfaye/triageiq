"""
Ticket service — business logic for user-facing ticket operations.
Orchestrates: ticket creation → AI analysis → persistence.
"""

import uuid
from collections.abc import Sequence

import structlog
from app.domain.entities.ticket import Ticket
from app.infrastructure.ai.openai_client import AIServiceError, get_openai_client
from app.repositories.ticket_repository import TicketRepository

log = structlog.get_logger(__name__)


class TicketService:
    def __init__(self, ticket_repo: TicketRepository) -> None:
        self._tickets = ticket_repo

    async def create_ticket(
        self,
        *,
        user_id: uuid.UUID,
        message: str,
    ) -> Ticket:
        """
        Create a ticket and enrich it with AI triage.
        If AI is unavailable, ticket is saved in degraded mode (no category/priority).
        AIServiceError is re-raised so the router can return a structured error
        while still returning the partially saved ticket ID.
        """
        ai_client = get_openai_client()
        ai_analysis = None
        ai_error: AIServiceError | None = None

        try:
            ai_analysis = await ai_client.analyze_ticket(message)
            log.info(
                "ticket_ai_analysis_complete",
                category=ai_analysis.category,
                priority=ai_analysis.priority,
            )
        except AIServiceError as e:
            log.error("ticket_ai_analysis_failed", error=str(e))
            ai_error = e

        ticket = await self._tickets.create(
            user_id=user_id,
            message=message,
            category=ai_analysis.category if ai_analysis else None,
            priority=ai_analysis.priority if ai_analysis else None,
            ai_response=ai_analysis.ai_response if ai_analysis else None,
            ai_raw=ai_analysis.model_dump() if ai_analysis else None,
        )

        if ai_error:
            raise ai_error  # re-raise with ticket already saved

        return ticket

    async def get_user_tickets(
        self,
        user_id: uuid.UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Ticket], int]:
        return await self._tickets.list_by_user(user_id, limit=limit, offset=offset)

    async def get_ticket_for_owner(
        self,
        ticket_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Ticket | None:
        """Enforce ownership — returns None if ticket doesn't exist or wrong owner."""
        return await self._tickets.get_by_id_and_user(ticket_id, user_id)

    async def get_user_stats(self, user_id: uuid.UUID) -> dict:
        return await self._tickets.get_stats_for_user(user_id)
