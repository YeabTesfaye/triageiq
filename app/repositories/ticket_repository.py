"""
Ticket repository — all database operations for the Ticket entity.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Sequence

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.ticket import Ticket
from app.domain.enums import TicketCategory, TicketPriority, TicketStatus


class TicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        message: str,
        category: Optional[TicketCategory] = None,
        priority: Optional[TicketPriority] = None,
        ai_response: Optional[str] = None,
        ai_raw: Optional[Dict[str, Any]] = None,
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

    async def get_by_id(self, ticket_id: uuid.UUID) -> Optional[Ticket]:
        stmt = select(Ticket).where(Ticket.id == ticket_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_and_user(
        self, ticket_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[Ticket]:
        """Enforce ownership — returns None if not owner."""
        stmt = select(Ticket).where(
            and_(Ticket.id == ticket_id, Ticket.user_id == user_id)
        )
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
        category: Optional[TicketCategory] = None,
        priority: Optional[TicketPriority] = None,
        status: Optional[TicketStatus] = None,
        user_id: Optional[uuid.UUID] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
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

        count_stmt = (
            select(func.count()).select_from(Ticket).where(where_clause)
        )
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

        stmt = (
            select(Ticket).where(where_clause).order_by(order).limit(limit).offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return rows, total

    async def update_status(
        self, ticket_id: uuid.UUID, status: TicketStatus
    ) -> Optional[Ticket]:
        from datetime import timezone
        stmt = (
            update(Ticket)
            .where(Ticket.id == ticket_id)
            .values(status=status.value, updated_at=datetime.now(timezone.utc))
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

    async def get_stats_for_user(self, user_id: uuid.UUID) -> Dict[str, Any]:
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
        stats: Dict[str, Any] = {"total": 0, "by_status": {}}
        for row in rows:
            stats["by_status"][row.status] = row.total
            stats["total"] += row.total
        return stats

    async def get_global_stats(self) -> Dict[str, Any]:
        """Global analytics for admin view."""
        total_stmt = select(func.count(Ticket.id))
        total = (await self._session.execute(total_stmt)).scalar_one()

        by_category_stmt = (
            select(Ticket.category, func.count(Ticket.id))
            .group_by(Ticket.category)
        )
        by_priority_stmt = (
            select(Ticket.priority, func.count(Ticket.id))
            .group_by(Ticket.priority)
        )
        by_status_stmt = (
            select(Ticket.status, func.count(Ticket.id))
            .group_by(Ticket.status)
        )

        by_cat = dict(
            (await self._session.execute(by_category_stmt)).all()
        )
        by_pri = dict(
            (await self._session.execute(by_priority_stmt)).all()
        )
        by_sta = dict(
            (await self._session.execute(by_status_stmt)).all()
        )

        return {
            "total": total,
            "by_category": by_cat,
            "by_priority": by_pri,
            "by_status": by_sta,
        }