"""
AuditLog repository — write-only audit trail.
Logs are NEVER updated or deleted via the application layer.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Sequence

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.audit_log import AuditLog
from app.domain.enums import AuditAction


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
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
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
        actor_id: Optional[uuid.UUID] = None,
        target_type: Optional[str] = None,
        action: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[AuditLog], int]:
        conditions = []
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

        where_clause = and_(*conditions) if conditions else True  # type: ignore

        count_stmt = (
            select(func.count()).select_from(AuditLog).where(where_clause)
        )
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