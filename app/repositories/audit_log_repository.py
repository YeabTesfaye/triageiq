"""
AuditLog repository — write-only audit trail.
Logs are NEVER updated or deleted via the application layer.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from app.domain.entities.audit_log import AuditLog
from app.domain.enums import AuditAction
from sqlalchemy import ColumnElement, and_, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        actor_id: uuid.UUID,
        actor_role: str,
        action: AuditAction,
        target_type: str,
        target_id: uuid.UUID,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        log = AuditLog(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action.value,
            target_type=target_type,
            target_id=target_id,
            before_state=before_state,
            after_state=after_state,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._session.add(log)
        await self._session.flush()
        return log

    async def list_logs(
        self,
        *,
        actor_id: uuid.UUID | None = None,
        target_type: str | None = None,
        action: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[AuditLog], int]:
        conditions: list[ColumnElement[bool]] = []
        if actor_id:
            conditions.append(AuditLog.actor_id == actor_id)
        if target_type:
            conditions.append(AuditLog.target_type == target_type)
        if action:
            conditions.append(AuditLog.action == action)
        if created_after:
            conditions.append(AuditLog.created_at >= created_after)
        if created_before:
            conditions.append(AuditLog.created_at <= created_before)

        where_clause = and_(*conditions) if conditions else true()  # type: ignore

        count_stmt = select(func.count()).select_from(AuditLog).where(where_clause)
        total = (await self._session.execute(count_stmt)).scalar_one()

        stmt = (
            select(AuditLog)
            .where(where_clause)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return rows, total
