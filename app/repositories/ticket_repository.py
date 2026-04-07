"""
Ticket repository — all database operations for the Ticket entity.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from app.domain.entities.ticket import Ticket
from app.domain.enums import TicketCategory, TicketPriority, TicketStatus
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession


class TicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        message: str,
        category: TicketCategory | None = None,
        priority: TicketPriority | None = None,
        ai_response: str | None = None,
        ai_raw: dict[str, Any] | None = None,
    ) -> Ticket:
        ticket = Ticket(
            user_id=user_id,
            message=message,
            category=category.value if category else None,
            priority=priority.value if priority else None,
            ai_response=ai_response,
            ai_raw=ai_raw,
            status=TicketStatus.OPEN.value,
        )
        self._session.add(ticket)
        await self._session.flush()
        return ticket

    async def get_by_id(self, ticket_id: uuid.UUID) -> Ticket | None:
        stmt = select(Ticket).where(Ticket.id == ticket_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_and_user(self, ticket_id: uuid.UUID, user_id: uuid.UUID) -> Ticket | None:
        """Enforce ownership — returns None if not owner."""
        stmt = select(Ticket).where(and_(Ticket.id == ticket_id, Ticket.user_id == user_id))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Ticket], int]:
        conditions = [Ticket.user_id == user_id]
        return await self._paginated_query(conditions, limit=limit, offset=offset)

    async def list_all(
        self,
        *,
        category: TicketCategory | None = None,
        priority: TicketPriority | None = None,
        status: TicketStatus | None = None,
        user_id: uuid.UUID | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Ticket], int]:
        conditions = []
        if category:
            conditions.append(Ticket.category == category.value)
        if priority:
            conditions.append(Ticket.priority == priority.value)
        if status:
            conditions.append(Ticket.status == status.value)
        if user_id:
            conditions.append(Ticket.user_id == user_id)
        if created_after:
            conditions.append(Ticket.created_at >= created_after)
        if created_before:
            conditions.append(Ticket.created_at <= created_before)

        return await self._paginated_query(
            conditions,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )

    async def _paginated_query(
        self,
        conditions: list,
        *,
        limit: int,
        offset: int,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> tuple[Sequence[Ticket], int]:
        where_clause = and_(*conditions) if conditions else True  # type: ignore

        count_stmt = select(func.count()).select_from(Ticket).where(where_clause)
        total = (await self._session.execute(count_stmt)).scalar_one()

        # Safe column mapping — avoid SQL injection from sort_by param
        sortable_columns = {
            "created_at": Ticket.created_at,
            "updated_at": Ticket.updated_at,
            "priority": Ticket.priority,
            "status": Ticket.status,
        }
        sort_col = sortable_columns.get(sort_by, Ticket.created_at)
        order = sort_col.desc() if sort_dir == "desc" else sort_col.asc()

        stmt = select(Ticket).where(where_clause).order_by(order).limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        return rows, total

    async def update_status(self, ticket_id: uuid.UUID, status: TicketStatus) -> Ticket | None:
        stmt = (
            update(Ticket)
            .where(Ticket.id == ticket_id)
            .values(status=status.value, updated_at=datetime.now(UTC))
            .returning(Ticket)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, ticket_id: uuid.UUID) -> bool:
        """Hard delete. Returns True if a row was deleted."""
        from sqlalchemy import delete as sa_delete

        stmt = sa_delete(Ticket).where(Ticket.id == ticket_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def get_stats_for_user(self, user_id: uuid.UUID) -> dict[str, Any]:
        """Per-user ticket statistics."""
        stmt = (
            select(
                func.count(Ticket.id).label("total"),
                Ticket.status,
            )
            .where(Ticket.user_id == user_id)
            .group_by(Ticket.status)
        )
        rows = (await self._session.execute(stmt)).all()
        stats: dict[str, Any] = {"total": 0, "by_status": {}}
        for row in rows:
            stats["by_status"][row.status] = row.total
            stats["total"] += row.total
        return stats

    async def get_global_stats(self) -> dict[str, Any]:
        """Global analytics for admin view."""
        total_stmt = select(func.count(Ticket.id))
        total = (await self._session.execute(total_stmt)).scalar_one()

        by_category_stmt = select(Ticket.category, func.count(Ticket.id)).group_by(Ticket.category)
        by_priority_stmt = select(Ticket.priority, func.count(Ticket.id)).group_by(Ticket.priority)
        by_status_stmt = select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status)

        by_cat: dict[str,int] = dict((await self._session.execute(by_category_stmt)).all())
        by_pri: dict[str,int] = dict((await self._session.execute(by_priority_stmt)).all())
        by_sta: dict[str,int] = dict((await self._session.execute(by_status_stmt)).all())

        return {
            "total": total,
            "by_category": by_cat,
            "by_priority": by_pri,
            "by_status": by_sta,
        }
