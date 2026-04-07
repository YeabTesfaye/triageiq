"""
Admin router — privileged endpoints for user and ticket management.

RBAC is enforced at the Depends() level — never inside route handlers.
Every state-mutating endpoint writes an audit log entry (handled by AdminService).
"""

import uuid
from datetime import datetime

from app.application.services.admin_service import AdminError, AdminService
from app.dependencies import (
    PaginationParams,
    get_client_ip,
    get_user_agent,
    require_roles,
)
from app.domain.entities.user import User
from app.domain.enums import Role, TicketCategory, TicketPriority, TicketStatus, UserStatus
from app.infrastructure.database import get_db_session
from app.presentation.schemas.admin_schemas import (
    AdminTicketListResponse,
    AdminTicketResponse,
    AdminUpdateTicketStatusRequest,
    AdminUserDetailResponse,
    AdminUserListResponse,
    AdminUserResponse,
    AuditLogListResponse,
    AuditLogResponse,
    ChangeRoleRequest,
    ChangeStatusRequest,
    PaginationMeta,
)
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.ticket_repository import TicketRepository
from app.repositories.user_repository import UserRepository
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/admin", tags=["Admin"])


def _get_admin_service(
    session: AsyncSession = Depends(get_db_session),
) -> AdminService:
    return AdminService(
        user_repo=UserRepository(session),
        ticket_repo=TicketRepository(session),
        token_repo=RefreshTokenRepository(session),
        audit_repo=AuditLogRepository(session),
    )


def _pagination_meta(total: int, limit: int, offset: int) -> PaginationMeta:
    return PaginationMeta(
        total=total,
        limit=limit,
        offset=offset,
        has_next=(offset + limit) < total,
        has_prev=offset > 0,
    )


# ── User Management ────────────────────────────────────────────────────────────


@router.get(
    "/users",
    response_model=AdminUserListResponse,
    summary="List all users with filters (ADMIN+)",
)
async def list_users(
    role: Role | None = Query(None),
    user_status: UserStatus | None = Query(None, alias="status"),
    created_after: datetime | None = Query(None),
    created_before: datetime | None = Query(None),
    pagination: PaginationParams = Depends(),
    _actor: User = Depends(require_roles(Role.ADMIN, Role.SUPERADMIN)),
    service: AdminService = Depends(_get_admin_service),
):
    users, total = await service.list_users(
        role=role,
        status=user_status,
        created_after=created_after,
        created_before=created_before,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return AdminUserListResponse(
        items=[AdminUserResponse.model_validate(u) for u in users],
        meta=_pagination_meta(total, pagination.limit, pagination.offset),
    )


@router.get(
    "/users/{user_id}",
    response_model=AdminUserDetailResponse,
    summary="Get user profile + ticket stats (ADMIN+)",
)
async def get_user(
    user_id: uuid.UUID,
    _actor: User = Depends(require_roles(Role.ADMIN, Role.SUPERADMIN)),
    service: AdminService = Depends(_get_admin_service),
):
    try:
        user, stats = await service.get_user_detail(user_id)
        response = AdminUserDetailResponse.model_validate(user)
        response.ticket_stats = stats
        return response
    except AdminError as e:
        if e.code == "USER_NOT_FOUND":
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch(
    "/users/{user_id}/role",
    response_model=AdminUserResponse,
    summary="Change a user's role (SUPERADMIN only)",
)
async def change_user_role(
    user_id: uuid.UUID,
    body: ChangeRoleRequest,
    request: Request,
    actor: User = Depends(require_roles(Role.SUPERADMIN)),
    service: AdminService = Depends(_get_admin_service),
):
    try:
        updated = await service.change_user_role(
            actor=actor,
            target_user_id=user_id,
            new_role=body.role,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
        return AdminUserResponse.model_validate(updated)
    except AdminError as e:
        code_map = {
            "USER_NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "FORBIDDEN_ROLE": status.HTTP_403_FORBIDDEN,
            "FORBIDDEN_TARGET": status.HTTP_403_FORBIDDEN,
            "SELF_MODIFY": status.HTTP_400_BAD_REQUEST,
        }
        raise HTTPException(code_map.get(e.code, status.HTTP_400_BAD_REQUEST), detail=str(e))


@router.patch(
    "/users/{user_id}/status",
    response_model=AdminUserResponse,
    summary="Change a user's status — suspend/ban invalidates sessions (ADMIN+)",
)
async def change_user_status(
    user_id: uuid.UUID,
    body: ChangeStatusRequest,
    request: Request,
    actor: User = Depends(require_roles(Role.ADMIN, Role.SUPERADMIN)),
    service: AdminService = Depends(_get_admin_service),
):
    try:
        updated = await service.change_user_status(
            actor=actor,
            target_user_id=user_id,
            new_status=body.status,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
        return AdminUserResponse.model_validate(updated)
    except AdminError as e:
        code_map = {
            "USER_NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "FORBIDDEN_TARGET": status.HTTP_403_FORBIDDEN,
            "SELF_MODIFY": status.HTTP_400_BAD_REQUEST,
        }
        raise HTTPException(code_map.get(e.code, status.HTTP_400_BAD_REQUEST), detail=str(e))


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a user (SUPERADMIN only)",
)
async def delete_user(
    user_id: uuid.UUID,
    request: Request,
    actor: User = Depends(require_roles(Role.SUPERADMIN)),
    service: AdminService = Depends(_get_admin_service),
):
    try:
        await service.delete_user(
            actor=actor,
            target_user_id=user_id,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
    except AdminError as e:
        code_map = {
            "USER_NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "FORBIDDEN_TARGET": status.HTTP_403_FORBIDDEN,
            "SELF_DELETE": status.HTTP_400_BAD_REQUEST,
        }
        raise HTTPException(code_map.get(e.code, status.HTTP_400_BAD_REQUEST), detail=str(e))


# ── Ticket Management ──────────────────────────────────────────────────────────


@router.get(
    "/tickets",
    response_model=AdminTicketListResponse,
    summary="List all tickets across all users (MODERATOR+)",
)
async def list_tickets(
    category: TicketCategory | None = Query(None),
    priority: TicketPriority | None = Query(None),
    ticket_status: TicketStatus | None = Query(None, alias="status"),
    user_id: uuid.UUID | None = Query(None),
    created_after: datetime | None = Query(None),
    created_before: datetime | None = Query(None),
    sort_by: str = Query("created_at", pattern="^(created_at|updated_at|priority|status)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    pagination: PaginationParams = Depends(),
    _actor: User = Depends(require_roles(Role.MODERATOR, Role.ADMIN, Role.SUPERADMIN)),
    service: AdminService = Depends(_get_admin_service),
):
    tickets, total = await service.list_tickets(
        category=category,
        priority=priority,
        status=ticket_status,
        user_id=user_id,
        created_after=created_after,
        created_before=created_before,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return AdminTicketListResponse(
        items=[AdminTicketResponse.model_validate(t) for t in tickets],
        meta=_pagination_meta(total, pagination.limit, pagination.offset),
    )


@router.patch(
    "/tickets/{ticket_id}/status",
    response_model=AdminTicketResponse,
    summary="Update ticket status (MODERATOR+)",
)
async def update_ticket_status(
    ticket_id: uuid.UUID,
    body: AdminUpdateTicketStatusRequest,
    request: Request,
    actor: User = Depends(require_roles(Role.MODERATOR, Role.ADMIN, Role.SUPERADMIN)),
    service: AdminService = Depends(_get_admin_service),
):
    try:
        updated = await service.update_ticket_status(
            actor=actor,
            ticket_id=ticket_id,
            new_status=body.status,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
        return AdminTicketResponse.model_validate(updated)
    except AdminError as e:
        if e.code == "TICKET_NOT_FOUND":
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/tickets/{ticket_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Hard-delete a ticket (ADMIN+)",
)
async def delete_ticket(
    ticket_id: uuid.UUID,
    request: Request,
    actor: User = Depends(require_roles(Role.ADMIN, Role.SUPERADMIN)),
    service: AdminService = Depends(_get_admin_service),
):
    try:
        await service.delete_ticket(
            actor=actor,
            ticket_id=ticket_id,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
    except AdminError as e:
        if e.code == "TICKET_NOT_FOUND":
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


# ── Audit Logs ─────────────────────────────────────────────────────────────────


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    summary="View audit trail (SUPERADMIN only)",
)
async def list_audit_logs(
    actor_id: uuid.UUID | None = Query(None),
    target_type: str | None = Query(None),
    action: str | None = Query(None),
    created_after: datetime | None = Query(None),
    created_before: datetime | None = Query(None),
    pagination: PaginationParams = Depends(),
    _actor: User = Depends(require_roles(Role.SUPERADMIN)),
    service: AdminService = Depends(_get_admin_service),
):
    logs, total = await service.list_audit_logs(
        actor_id=actor_id,
        target_type=target_type,
        action=action,
        created_after=created_after,
        created_before=created_before,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(log) for log in logs],
        meta=_pagination_meta(total, pagination.limit, pagination.offset),
    )
