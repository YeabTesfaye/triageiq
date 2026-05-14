"""
Ticket repository — all database operations for the Ticket entity.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Literal

from app.domain.entities.ticket import Ticket
from app.domain.enums import TicketCategory, TicketPriority, TicketStatus
from sqlalchemy import ColumnElement, and_, func, select, true, update
from sqlalchemy.engine import CursorResult
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
        user_id,
        *,
        limit: int = 20,
        offset: int = 0,
        status: TicketStatus | None = None,
        priority: Literal["high", "medium", "low"] | None = None,
        search: str | None = None,
        sort: Literal["created_at", "priority"] = "created_at",
        order: Literal["asc", "desc"] = "desc",
    ) -> tuple[Sequence[Ticket], int]:
        """
        Return (tickets, total_count) for a user, with optional server-side
        filtering, full-text search, and sorting.

        total_count reflects the filtered set so the frontend can paginate
        correctly over the filtered results rather than over all tickets.
        """
        base: Select = select(Ticket).where(Ticket.user_id == user_id)

        # ── Filters ───────────────────────────────────────────────────────────────
        if status is not None:
            base = base.where(Ticket.status == status)

        if priority is not None:
            base = base.where(Ticket.priority == priority)

        if search:
            # Case-insensitive substring match across message and category.
            # For production at scale, replace with a tsvector/GIN index query.
            term = f"%{search.lower()}%"
            base = base.where(Ticket.message.ilike(term) | Ticket.category.ilike(term))

        # ── Total (before pagination) ─────────────────────────────────────────────
        count_q = select(func.count()).select_from(base.subquery())
        total: int = (await self._session.execute(count_q)).scalar_one()

        # ── Sort ──────────────────────────────────────────────────────────────────
        sort_col = Ticket.created_at if sort == "created_at" else Ticket.priority

        # Priority has non-alphabetical semantics: high > medium > low.
        # We map it to an integer so ORDER BY works correctly regardless of
        # whether priority is stored as a plain string.
        if sort == "priority":
            from sqlalchemy import case

            priority_rank = case(
                (Ticket.priority == "high", 1),
                (Ticket.priority == "medium", 2),
                (Ticket.priority == "low", 3),
                else_=4,
            )
            sort_expr = priority_rank.asc() if order == "asc" else priority_rank.desc()
        else:
            sort_expr = sort_col.asc() if order == "asc" else sort_col.desc()

        query = base.order_by(sort_expr).limit(limit).offset(offset)

        # ── Execute ───────────────────────────────────────────────────────────────
        rows = (await self._session.execute(query)).scalars().all()
        return rows, total

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
        conditions: list[ColumnElement[bool]] = []
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
        conditions: list[ColumnElement[bool]],
        *,
        limit: int,
        offset: int,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> tuple[Sequence[Ticket], int]:
        where_clause = and_(*conditions) if conditions else true()
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
        assert isinstance(result, CursorResult)
        return result.rowcount > 0

    async def update_ai_fields(
        self,
        ticket_id: uuid.UUID,
        ai_analysis,  # TicketAnalysis from your openai_client
    ) -> Ticket | None:
        stmt = (
            update(Ticket)
            .where(Ticket.id == ticket_id)
            .values(
                category=ai_analysis.category.value if ai_analysis.category else None,
                priority=ai_analysis.priority.value if ai_analysis.priority else None,
                ai_response=ai_analysis.ai_response,
                ai_raw=ai_analysis.model_dump(),
                updated_at=datetime.now(UTC),
            )
            .returning(Ticket)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_stats_for_user(self, user_id: uuid.UUID) -> dict[str, Any]:
        """Per-user ticket statistics — matches global stats shape."""
        base = Ticket.user_id == user_id

        by_status_stmt = (
            select(Ticket.status, func.count(Ticket.id)).where(base).group_by(Ticket.status)
        )
        by_category_stmt = (
            select(Ticket.category, func.count(Ticket.id)).where(base).group_by(Ticket.category)
        )
        by_priority_stmt = (
            select(Ticket.priority, func.count(Ticket.id)).where(base).group_by(Ticket.priority)
        )
        ai_processing_stmt = select(func.count(Ticket.id)).where(
            and_(base, Ticket.category.is_(None), Ticket.ai_raw.is_(None))
        )

        by_sta: dict[str, int] = {
            row[0]: row[1] for row in (await self._session.execute(by_status_stmt)).all()
        }
        by_cat: dict[str, int] = {
            row[0]: row[1] for row in (await self._session.execute(by_category_stmt)).all()
        }
        by_pri: dict[str, int] = {
            row[0]: row[1] for row in (await self._session.execute(by_priority_stmt)).all()
        }
        ai_processing = (await self._session.execute(ai_processing_stmt)).scalar_one()

        # Remove None key that appears for tickets pending AI enrichment
        by_cat.pop(None, None)
        by_pri.pop(None, None)

        return {
            "total": sum(by_sta.values()),
            "ai_processing": ai_processing,
            "by_status": {k: v for k, v in by_sta.items() if k},  # keep (has condition)
            "by_category": dict(by_cat),  # ✅ fixed
            "by_priority": dict(by_pri),  # ✅ fixed
        }

    async def get_global_stats(self) -> dict[str, Any]:
        """Global analytics — 2 queries instead of 4."""
        # Single query for all group-by breakdowns
        breakdown_stmt = select(
            Ticket.status,
            Ticket.category,
            Ticket.priority,
            func.count(Ticket.id).label("cnt"),
        ).group_by(Ticket.status, Ticket.category, Ticket.priority)

        rows = (await self._session.execute(breakdown_stmt)).all()

        by_sta: dict[str, int] = {}
        by_cat: dict[str, int] = {}
        by_pri: dict[str, int] = {}
        total = 0

        for status, category, priority, cnt in rows:
            total += cnt
            by_sta[status] = by_sta.get(status, 0) + cnt
            if category:
                by_cat[category] = by_cat.get(category, 0) + cnt
            if priority:
                by_pri[priority] = by_pri.get(priority, 0) + cnt

        # Tickets still pending AI enrichment
        ai_processing_stmt = select(func.count(Ticket.id)).where(
            and_(Ticket.category.is_(None), Ticket.ai_raw.is_(None))
        )
        ai_processing = (await self._session.execute(ai_processing_stmt)).scalar_one()

        return {
            "total": total,
            "ai_processing": ai_processing,
            "by_status": by_sta,
            "by_category": by_cat,
            "by_priority": by_pri,
        }
