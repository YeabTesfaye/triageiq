"""
Chat repository.

Handles all database I/O for the ``messages`` table.
Follows the repository pattern used throughout this codebase:
  - Accepts an ``AsyncSession`` in ``__init__``.
  - Uses ``select()`` queries exclusively.
  - Returns typed domain objects.
  - Never raises HTTP exceptions.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.message import Message


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
        await self._session.flush()   # populate server-defaults (id, created_at)
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
        offset: int = 0,
    ) -> tuple[Sequence[Message], int]:
        """
        Return a page of messages for *ticket_id*, ordered oldest-first,
        along with the total un-paginated count.
        """
        base_filter = Message.ticket_id == ticket_id

        # Total count
        count_stmt = select(func.count()).select_from(Message).where(base_filter)
        total: int = (await self._session.execute(count_stmt)).scalar_one()

        # Page of rows
        rows_stmt = (
            select(Message)
            .where(base_filter)
            .order_by(Message.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        rows: Sequence[Message] = (await self._session.scalars(rows_stmt)).all()

        return rows, total