"""
Ticket service — business logic for user-facing ticket operations.
Orchestrates: ticket creation → AI analysis → persistence.
"""

import uuid
from collections.abc import Sequence
from typing import Literal

import structlog
from app.domain.entities.ticket import Ticket
from app.domain.enums import TicketStatus
from app.infrastructure.ai.openai_client import AIServiceError, get_openai_client
from app.repositories.ticket_repository import TicketRepository

log = structlog.get_logger(__name__)


class TicketService:
    def __init__(self, ticket_repo: TicketRepository) -> None:
        self._tickets = ticket_repo

    async def get_user_tickets(
        self,
        user_id: uuid.UUID,
        *,
        limit: int = 20,
        offset: int = 0,
        status: TicketStatus | None = None,
        priority: Literal["high", "medium", "low"] | None = None,
        search: str | None = None,
        sort: Literal["created_at", "priority"] = "created_at",
        order: Literal["asc", "desc"] = "desc",
    ) -> tuple[Sequence[Ticket], int]:
        return await self._tickets.list_by_user(
            user_id,
            limit=limit,
            offset=offset,
            status=status,
            priority=priority,
            search=search,
            sort=sort,
            order=order,
        )

    async def get_ticket_for_owner(
        self,
        ticket_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Ticket | None:
        """Enforce ownership — returns None if ticket doesn't exist or wrong owner."""
        return await self._tickets.get_by_id_and_user(ticket_id, user_id)

    async def get_user_stats(self, user_id: uuid.UUID) -> dict:
        return await self._tickets.get_stats_for_user(user_id)

    async def delete_ticket_for_owner(
        self,
        ticket_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """
        Delete a ticket if it belongs to the user.
        Returns False if not found or not owner.
        """
        ticket = await self._tickets.get_by_id_and_user(ticket_id, user_id)
        if ticket is None:
            return False
        return await self._tickets.delete(ticket_id)

    async def update_ticket_status_for_owner(
        self,
        ticket_id: uuid.UUID,
        user_id: uuid.UUID,
        status: TicketStatus,
    ) -> Ticket | None:
        """
        Update ticket status if owned by user.
        Returns None if not found or not owner.
        """
        ticket = await self._tickets.get_by_id_and_user(ticket_id, user_id)
        if ticket is None:
            return None
        return await self._tickets.update_status(ticket_id, status)

    async def create_ticket_pending(
        self,
        *,
        user_id: uuid.UUID,
        message: str,
    ) -> Ticket:
        """Save ticket immediately with no AI enrichment yet."""
        return await self._tickets.create(
            user_id=user_id,
            message=message,
        )

    async def run_ai_analysis(self, ticket_id: uuid.UUID) -> None:
        """
        Called from BackgroundTasks after the 202 is already sent.
        Enriches the saved ticket with AI results.
        Failures are logged but not re-raised — the ticket stays in degraded mode.
        """
        ticket = await self._tickets.get_by_id(ticket_id)
        if ticket is None:
            log.error("bg_ai_analysis_ticket_not_found", ticket_id=str(ticket_id))
            return

        ai_client = get_openai_client()
        try:
            ai_analysis = await ai_client.analyze_ticket(ticket.message)
            await self._tickets.update_ai_fields(ticket_id, ai_analysis)
            log.info(
                "bg_ai_analysis_complete",
                ticket_id=str(ticket_id),
                category=ai_analysis.category,
                priority=ai_analysis.priority,
            )
        except AIServiceError as e:
            log.error("bg_ai_analysis_failed", ticket_id=str(ticket_id), error=str(e))
