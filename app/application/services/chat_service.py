"""
Chat application service.

Flow:
  1. Validate ticket access
  2. Persist the user's message   (PostgreSQL — must succeed)
  3. Generate an AI reply via OpenAI
  4. Persist the AI reply          (PostgreSQL — must succeed)
  5. Broadcast both to Firebase    (non-fatal)
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import structlog
from app.domain.entities.message import Message
from app.infrastructure.ai.openai_client import AIServiceError, get_openai_client
from app.infrastructure.firebase_client import push_message_to_firebase
from app.repositories.chat_repository import ChatRepository

log = structlog.get_logger(__name__)

AI_SENDER_ROLE = "assistant"


class ChatError(Exception):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class ChatService:
    def __init__(self, chat_repo: ChatRepository, ticket_repo) -> None:
        self._chat_repo = chat_repo
        self._ticket_repo = ticket_repo

    async def _resolve_ticket(self, ticket_id, requester_id, *, is_admin):
        if is_admin:
            ticket = await self._ticket_repo.get_by_id(ticket_id)
        else:
            ticket = await self._ticket_repo.get_by_id_and_user(ticket_id, requester_id)
        if ticket is None:
            raise ChatError("Ticket not found", code="TICKET_NOT_FOUND")
        return ticket

    async def _broadcast(self, ticket_id: uuid.UUID, message: Message) -> None:
        payload = {
            "id": str(message.id),
            "ticket_id": str(ticket_id),
            "sender_role": message.sender_role,
            "content": message.content,
            "created_at": message.created_at.isoformat(),
        }
        await push_message_to_firebase(str(ticket_id), payload)

    async def send_message(
        self,
        *,
        ticket_id: uuid.UUID,
        sender_id: uuid.UUID,
        sender_role,
        content: str,
        is_admin: bool,
    ) -> tuple[Message, Message | None]:
        """
        Save user message → get AI reply → save AI reply.
        Returns (user_message, ai_message).
        ai_message is None if OpenAI is unavailable — HTTP still returns 201.
        """
        ticket = await self._resolve_ticket(ticket_id, sender_id, is_admin=is_admin)

        # Normalise role enum → string
        role_str = sender_role.value if hasattr(sender_role, "value") else str(sender_role)

        # 1. Persist user message
        user_msg = await self._chat_repo.create(
            ticket_id=ticket_id,
            sender_id=sender_id,
            sender_role=role_str,
            content=content,
        )
        log.info(
            "chat_service.user_message_saved", ticket_id=str(ticket_id), message_id=str(user_msg.id)
        )
        await self._broadcast(ticket_id, user_msg)

        # 2. Build conversation history for the AI (last 10 messages)
        recent, _ = await self._chat_repo.list_by_ticket(ticket_id, limit=10, offset=0)
        history = [
            {
                "role": "assistant" if m.sender_role == AI_SENDER_ROLE else "user",
                "content": m.content,
            }
            for m in recent
        ]

        # 3. Generate + persist AI reply (non-fatal)
        ai_msg: Message | None = None
        try:
            client = get_openai_client()
            ticket_description = getattr(ticket, "description", "") or ""
            ai_text = await client.chat_reply(
                ticket_description=ticket_description,
                history=history,
            )
            ai_msg = await self._chat_repo.create(
                ticket_id=ticket_id,
                sender_id=None,
                sender_role=AI_SENDER_ROLE,
                content=ai_text,
            )
            log.info(
                "chat_service.ai_reply_saved", ticket_id=str(ticket_id), message_id=str(ai_msg.id)
            )
            await self._broadcast(ticket_id, ai_msg)

        except AIServiceError:
            log.warning("chat_service.ai_unavailable", ticket_id=str(ticket_id))
        except Exception:
            log.exception("chat_service.ai_error", ticket_id=str(ticket_id))

        return user_msg, ai_msg

    async def get_messages(
        self,
        *,
        ticket_id: uuid.UUID,
        requester_id: uuid.UUID,
        is_admin: bool,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Message], int]:
        await self._resolve_ticket(ticket_id, requester_id, is_admin=is_admin)
        return await self._chat_repo.list_by_ticket(ticket_id, limit=limit, offset=offset)
