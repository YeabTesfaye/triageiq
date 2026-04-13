"""
Chat repository.
Handles all database I/O for the ``messages`` table.

Design principles followed:
  - Repository pattern: all DB I/O is here; service layer stays pure.
  - Cursor pagination (before_id) instead of offset: offset breaks under
    real-time inserts (rows shift), cursor is stable regardless of new messages.
  - Two queries (count + page): gives the client a total for UI "X unread"
    indicators without a second HTTP call.
  - Results are reversed after the DESC fetch so callers always receive
    messages in ascending (chronological) order.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from app.domain.entities.message import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def create(
        self,
        *,
        ticket_id: uuid.UUID,
        sender_id: uuid.UUID | None,
        sender_role: str,
        content: str,
    ) -> Message:
        """Persist a new message and return the fully-populated ORM object."""
        message = Message(
            ticket_id=ticket_id,
            sender_id=sender_id,
            sender_role=sender_role,
            content=content,
        )
        self._session.add(message)
        # flush populates server-defaults (id, created_at) without committing —
        # the calling service controls the transaction boundary.
        await self._session.flush()
        await self._session.refresh(message)
        return message

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def list_by_ticket(
        self,
        ticket_id: uuid.UUID,
        *,
        limit: int = 50,
        before_id: uuid.UUID | None = None,
        offset: int | None = None,
    ) -> tuple[Sequence[Message], int]:
        """
        Return a page of messages for *ticket_id*, ordered oldest-first,
        along with the total un-paginated count.

        Cursor pagination via before_id:
          - No before_id  → return the latest `limit` messages (initial load).
          - With before_id → return `limit` messages older than that message
                            (scroll-up / "load more" pattern).

        The count always reflects the full thread so the client can show
        "showing 50 of 120 messages" without a second request.
        """
        base_filter = Message.ticket_id == ticket_id

        if before_id is not None:
            # Resolve the cursor row's timestamp — using created_at keeps the
            # filter index-friendly (ix_messages_created_at).
            cursor_stmt = select(Message.created_at).where(Message.id == before_id)
            cursor_ts = (await self._session.execute(cursor_stmt)).scalar_one_or_none()
            if cursor_ts is not None:
                base_filter = base_filter & (Message.created_at < cursor_ts)

        # Total count for the whole thread (ignoring cursor) so pagination UI
        # always shows the correct total even when loading older pages.
        total_filter = Message.ticket_id == ticket_id
        count_stmt = select(func.count()).select_from(Message).where(total_filter)
        total: int = (await self._session.execute(count_stmt)).scalar_one()

        # Fetch newest-first (DESC) so LIMIT efficiently trims at the "top",
        # then reverse so callers always receive chronological (ASC) order.
        rows_stmt = (
            select(Message).where(base_filter).order_by(Message.created_at.desc()).limit(limit)
        )
        rows: Sequence[Message] = (await self._session.scalars(rows_stmt)).all()
        return list(reversed(rows)), total
