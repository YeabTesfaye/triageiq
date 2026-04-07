"""
Admin service — privileged operations with mandatory audit trail.

Every state-mutating method:
1. Validates business rules (e.g., cannot demote SUPERADMIN)
2. Performs the DB mutation via repository
3. Writes an immutable AuditLog entry
4. Invalidates Redis sessions if needed

No DB calls or Redis calls outside repository/infra layers.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

import structlog
from app.domain.entities.audit_log import AuditLog
from app.domain.entities.ticket import Ticket
from app.domain.entities.user import User
from app.domain.enums import AuditAction, Role, TicketStatus, UserStatus
from app.infrastructure.redis_client import blacklist_all_user_tokens
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.ticket_repository import TicketRepository
from app.repositories.user_repository import UserRepository

log = structlog.get_logger(__name__)

# Session cutoff TTL: keep per-user invalidation for 7 days (max refresh token life)
_SESSION_CUTOFF_TTL = 7 * 24 * 60 * 60


class AdminError(Exception):
    """Business rule violation in admin operations."""

    def __init__(self, message: str, code: str = "ADMIN_ERROR"):
        super().__init__(message)
        self.code = code


def _user_snapshot(user: User) -> dict[str, Any]:
    """Safe snapshot for audit log — excludes password_hash."""
    return {
        "id": str(user.id),
        "email": f"***{user.email[-6:]}",  # mask PII
        "role": user.role,
        "status": user.status,
        "is_verified": user.is_verified,
        "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None,
    }


def _ticket_snapshot(ticket: Ticket) -> dict[str, Any]:
    return {
        "id": str(ticket.id),
        "status": ticket.status,
        "category": ticket.category,
        "priority": ticket.priority,
    }


class AdminService:
    def __init__(
        self,
        user_repo: UserRepository,
        ticket_repo: TicketRepository,
        token_repo: RefreshTokenRepository,
        audit_repo: AuditLogRepository,
    ) -> None:
        self._users = user_repo
        self._tickets = ticket_repo
        self._tokens = token_repo
        self._audit = audit_repo

    # ── User Listing ───────────────────────────────────────────────────────────

    async def list_users(
        self,
        *,
        role: Role | None = None,
        status: UserStatus | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[User], int]:
        return await self._users.list_users(
            role=role,
            status=status,
            created_after=created_after,
            created_before=created_before,
            limit=limit,
            offset=offset,
        )

    async def get_user_detail(self, user_id: uuid.UUID) -> tuple[User, dict[str, Any]]:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise AdminError("User not found", code="USER_NOT_FOUND")
        stats = await self._tickets.get_stats_for_user(user_id)
        return user, stats

    # ── Role Management ────────────────────────────────────────────────────────

    async def change_user_role(
        self,
        *,
        actor: User,
        target_user_id: uuid.UUID,
        new_role: Role,
        ip_address: str,
        user_agent: str,
    ) -> User:
        """
        Change a user's role.
        Business rules:
        - Only SUPERADMIN may call this
        - Cannot promote to SUPERADMIN via API
        - Cannot demote another SUPERADMIN
        - Cannot change own role
        """
        if new_role == Role.SUPERADMIN:
            raise AdminError(
                "Cannot promote to SUPERADMIN via API. Use direct DB seeding.",
                code="FORBIDDEN_ROLE",
            )

        target = await self._users.get_by_id(target_user_id)
        if target is None:
            raise AdminError("User not found", code="USER_NOT_FOUND")

        if target.id == actor.id:
            raise AdminError("Cannot change your own role", code="SELF_MODIFY")

        if target.role_enum == Role.SUPERADMIN:
            raise AdminError(
                "Cannot change the role of a SUPERADMIN",
                code="FORBIDDEN_TARGET",
            )

        before = _user_snapshot(target)
        updated = await self._users.update_role(target_user_id, new_role)
        if updated is None:
            raise AdminError("Role update failed", code="UPDATE_FAILED")

        await self._audit.create(
            actor_id=actor.id,
            actor_role=actor.role,
            action=AuditAction.USER_ROLE_CHANGE,
            target_type="user",
            target_id=target_user_id,
            before_state=before,
            after_state=_user_snapshot(updated),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        log.info(
            "admin_role_change",
            actor_id=str(actor.id),
            target_id=str(target_user_id),
            new_role=new_role.value,
        )
        return updated

    # ── Status Management ──────────────────────────────────────────────────────

    async def change_user_status(
        self,
        *,
        actor: User,
        target_user_id: uuid.UUID,
        new_status: UserStatus,
        ip_address: str,
        user_agent: str,
    ) -> User:
        """
        Change a user's status.
        On suspend/ban: all active sessions are immediately invalidated.
        """
        target = await self._users.get_by_id(target_user_id)
        if target is None:
            raise AdminError("User not found", code="USER_NOT_FOUND")

        if target.id == actor.id:
            raise AdminError("Cannot change your own status", code="SELF_MODIFY")

        # ADMIN cannot act on SUPERADMIN
        if target.role_enum == Role.SUPERADMIN and actor.role_enum != Role.SUPERADMIN:
            raise AdminError(
                "Insufficient privileges to modify a SUPERADMIN",
                code="FORBIDDEN_TARGET",
            )

        before = _user_snapshot(target)
        updated = await self._users.update_status(target_user_id, new_status)
        if updated is None:
            raise AdminError("Status update failed", code="UPDATE_FAILED")

        # Immediately invalidate all sessions if suspending or banning
        if new_status in (UserStatus.SUSPENDED, UserStatus.BANNED):
            await self._tokens.revoke_all_for_user(target_user_id)
            await blacklist_all_user_tokens(str(target_user_id), _SESSION_CUTOFF_TTL)
            log.info(
                "admin_sessions_invalidated",
                target_id=str(target_user_id),
                reason=new_status.value,
            )

        await self._audit.create(
            actor_id=actor.id,
            actor_role=actor.role,
            action=AuditAction.USER_STATUS_CHANGE,
            target_type="user",
            target_id=target_user_id,
            before_state=before,
            after_state=_user_snapshot(updated),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        log.info(
            "admin_status_change",
            actor_id=str(actor.id),
            target_id=str(target_user_id),
            new_status=new_status.value,
        )
        return updated

    # ── User Deletion ──────────────────────────────────────────────────────────

    async def delete_user(
        self,
        *,
        actor: User,
        target_user_id: uuid.UUID,
        ip_address: str,
        user_agent: str,
    ) -> None:
        """
        Soft-delete a user.
        - Cannot delete self
        - Cannot delete another SUPERADMIN
        - Invalidates all sessions
        """
        if actor.id == target_user_id:
            raise AdminError("Cannot delete your own account", code="SELF_DELETE")

        target = await self._users.get_by_id(target_user_id)
        if target is None:
            raise AdminError("User not found", code="USER_NOT_FOUND")

        if target.role_enum == Role.SUPERADMIN:
            raise AdminError(
                "Cannot delete a SUPERADMIN account",
                code="FORBIDDEN_TARGET",
            )

        before = _user_snapshot(target)
        deleted = await self._users.soft_delete(target_user_id)
        if deleted is None:
            raise AdminError("Delete failed", code="DELETE_FAILED")

        # Invalidate all sessions
        await self._tokens.revoke_all_for_user(target_user_id)
        await blacklist_all_user_tokens(str(target_user_id), _SESSION_CUTOFF_TTL)

        await self._audit.create(
            actor_id=actor.id,
            actor_role=actor.role,
            action=AuditAction.USER_DELETE,
            target_type="user",
            target_id=target_user_id,
            before_state=before,
            after_state={"deleted": True},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        log.info(
            "admin_user_deleted",
            actor_id=str(actor.id),
            target_id=str(target_user_id),
        )

    # ── Ticket Admin Operations ────────────────────────────────────────────────

    async def list_tickets(
        self,
        *,
        category=None,
        priority=None,
        status=None,
        user_id=None,
        created_after=None,
        created_before=None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Ticket], int]:
        return await self._tickets.list_all(
            category=category,
            priority=priority,
            status=status,
            user_id=user_id,
            created_after=created_after,
            created_before=created_before,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )

    async def update_ticket_status(
        self,
        *,
        actor: User,
        ticket_id: uuid.UUID,
        new_status: TicketStatus,
        ip_address: str,
        user_agent: str,
    ) -> Ticket:
        ticket = await self._tickets.get_by_id(ticket_id)
        if ticket is None:
            raise AdminError("Ticket not found", code="TICKET_NOT_FOUND")

        before = _ticket_snapshot(ticket)
        updated = await self._tickets.update_status(ticket_id, new_status)
        if updated is None:
            raise AdminError("Status update failed", code="UPDATE_FAILED")

        await self._audit.create(
            actor_id=actor.id,
            actor_role=actor.role,
            action=AuditAction.TICKET_STATUS_CHANGE,
            target_type="ticket",
            target_id=ticket_id,
            before_state=before,
            after_state=_ticket_snapshot(updated),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return updated

    async def delete_ticket(
        self,
        *,
        actor: User,
        ticket_id: uuid.UUID,
        ip_address: str,
        user_agent: str,
    ) -> None:
        ticket = await self._tickets.get_by_id(ticket_id)
        if ticket is None:
            raise AdminError("Ticket not found", code="TICKET_NOT_FOUND")

        before = _ticket_snapshot(ticket)
        deleted = await self._tickets.delete(ticket_id)
        if not deleted:
            raise AdminError("Delete failed", code="DELETE_FAILED")

        await self._audit.create(
            actor_id=actor.id,
            actor_role=actor.role,
            action=AuditAction.TICKET_DELETE,
            target_type="ticket",
            target_id=ticket_id,
            before_state=before,
            after_state=None,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        log.info(
            "admin_ticket_deleted",
            actor_id=str(actor.id),
            ticket_id=str(ticket_id),
        )

    # ── Audit Log Access ───────────────────────────────────────────────────────

    async def list_audit_logs(
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
        return await self._audit.list_logs(
            actor_id=actor_id,
            target_type=target_type,
            action=action,
            created_after=created_after,
            created_before=created_before,
            limit=limit,
            offset=offset,
        )
