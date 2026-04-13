"""
Chat application service.

Flow for send_message:
  1. Validate ticket access + closed guard
  2. Persist user message (PostgreSQL)
  3. Broadcast to Firebase
  4. Schedule AI reply as BackgroundTask (response sent here)
     a. Fresh session via session_factory
     b. Fetch recent history, call OpenAI, persist AI reply
     c. Broadcast AI reply to Firebase
"""
from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence

import structlog
from fastapi import BackgroundTasks

from app.domain.entities.message import Message
from app.domain.entities.ticket import Ticket
from app.infrastructure.ai.openai_client import get_openai_client
from app.infrastructure.firebase_client import push_message_to_firebase
from app.repositories.chat_repository import ChatRepository

log = structlog.get_logger(__name__)

AI_SENDER_ROLE = "assistant"
_CLOSED_STATUSES: frozenset[str] = frozenset({"closed"})


class ChatError(Exception):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class ChatService:
    def __init__(
        self,
        chat_repo: ChatRepository,
        ticket_repo,
        session_factory: Callable,
    ) -> None:
        self._chat_repo = chat_repo
        self._ticket_repo = ticket_repo
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _resolve_ticket(
        self,
        ticket_id: uuid.UUID,
        requester_id: uuid.UUID,
        *,
        is_admin: bool,
    ) -> Ticket:
        if is_admin:
            ticket = await self._ticket_repo.get_by_id(ticket_id)
        else:
            ticket = await self._ticket_repo.get_by_id_and_user(ticket_id, requester_id)
        if ticket is None:
            raise ChatError("Ticket not found", code="TICKET_NOT_FOUND")
        return ticket

    async def _broadcast(self, ticket_id: uuid.UUID, message: Message) -> None:
        """Push to Firebase. Non-fatal — log and continue on failure."""
        try:
            payload = {
                "id": str(message.id),
                "ticket_id": str(ticket_id),
                "sender_id": str(message.sender_id) if message.sender_id else None,
                "sender_role": message.sender_role,
                "is_ai": message.sender_role == AI_SENDER_ROLE,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            }
            await push_message_to_firebase(str(ticket_id), payload)
        except Exception:
            log.exception(
                "chat_service.firebase_broadcast_failed",
                ticket_id=str(ticket_id),
                message_id=str(message.id),
            )

    async def _generate_and_broadcast_ai_reply(
        self,
        *,
        ticket_id: uuid.UUID,
        ticket_description: str,
    ) -> None:
        """
        Background task — runs after HTTP response is sent.
        Opens its own session because the request-scoped session is closed.
        Only broadcasts after commit so we never push uncommitted data.
        """
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    repo = ChatRepository(session)
                    recent, _ = await repo.list_by_ticket(ticket_id, limit=10)
                    history = [
                        {
                            "role": "assistant" if m.sender_role == AI_SENDER_ROLE else "user",
                            "content": m.content,
                        }
                        for m in recent
                    ]
                    client = get_openai_client()
                    ai_text = await client.chat_reply(
                        ticket_description=ticket_description,
                        history=history,
                    )
                    ai_msg = await repo.create(
                        ticket_id=ticket_id,
                        sender_id=None,
                        sender_role=AI_SENDER_ROLE,
                        content=ai_text,
                    )
            # Broadcast after commit — data is durable before Firebase gets it
            await self._broadcast(ticket_id, ai_msg)
            log.info("chat_service.ai_reply_sent", ticket_id=str(ticket_id))
        except Exception:
            log.exception("chat_service.ai_reply_failed", ticket_id=str(ticket_id))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def send_message(
        self,
        *,
        ticket_id: uuid.UUID,
        sender_id: uuid.UUID,
        sender_role,
        content: str,
        is_admin: bool,
        background_tasks: BackgroundTasks,
    ) -> Message:
        ticket = await self._resolve_ticket(ticket_id, sender_id, is_admin=is_admin)

        if ticket.status in _CLOSED_STATUSES:
            raise ChatError("Ticket is closed", code="TICKET_CLOSED")

        role_str = sender_role.value if hasattr(sender_role, "value") else str(sender_role)

        user_msg = await self._chat_repo.create(
            ticket_id=ticket_id,
            sender_id=sender_id,
            sender_role=role_str,
            content=content,
        )
        await self._broadcast(ticket_id, user_msg)

        background_tasks.add_task(
            self._generate_and_broadcast_ai_reply,
            ticket_id=ticket_id,
            ticket_description=ticket.message or "",
        )
        return user_msg

    async def get_messages(
        self,
        *,
        ticket_id: uuid.UUID,
        requester_id: uuid.UUID,
        is_admin: bool,
        limit: int = 50,
        before_id: uuid.UUID | None = None,
    ) -> tuple[Sequence[Message], int]:
        await self._resolve_ticket(ticket_id, requester_id, is_admin=is_admin)
        return await self._chat_repo.list_by_ticket(
            ticket_id, limit=limit, before_id=before_id
        )

    async def get_thread(
        self,
        *,
        ticket_id: uuid.UUID,
        requester_id: uuid.UUID,
        is_admin: bool,
        limit: int = 50,
    ) -> tuple[object, Sequence[Message], int]:
        """
        Returns (ticket, messages, total) for the "open chat window" call.
        Validates access once and reuses the ticket object — no double query.
        """
        ticket = await self._resolve_ticket(ticket_id, requester_id, is_admin=is_admin)
        messages, total = await self._chat_repo.list_by_ticket(ticket_id, limit=limit)
        return ticket, messages, total