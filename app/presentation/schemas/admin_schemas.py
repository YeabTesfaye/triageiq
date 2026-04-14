"""
Admin schemas — request/response models for all admin endpoints.
"""

import uuid
from datetime import datetime
from typing import Any

from app.domain.enums import Role, TicketStatus, UserStatus
from pydantic import BaseModel, Field

# ── Pagination ─────────────────────────────────────────────────────────────────


class PaginationMeta(BaseModel):
    total: int
    limit: int
    offset: int
    has_next: bool
    has_prev: bool


# ── User Management ────────────────────────────────────────────────────────────


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    status: str
    is_verified: bool
    last_login_at: datetime | None
    failed_login_attempts: int
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminUserDetailResponse(AdminUserResponse):
    """Extended profile with ticket summary stats."""

    ticket_stats: dict[str, Any] = Field(default_factory=dict)


class AdminUserListResponse(BaseModel):
    items: list[AdminUserResponse]
    meta: PaginationMeta


class ChangeRoleRequest(BaseModel):
    role: Role

    @property
    def is_superadmin_attempt(self) -> bool:
        return self.role == Role.SUPERADMIN


class ChangeStatusRequest(BaseModel):
    status: UserStatus


# ── Ticket Management ──────────────────────────────────────────────────────────


class AdminTicketResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    message: str
    category: str | None
    priority: str | None
    ai_response: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminTicketListResponse(BaseModel):
    items: list[AdminTicketResponse]
    meta: PaginationMeta


class AdminUpdateTicketStatusRequest(BaseModel):
    status: TicketStatus


# ── Audit Logs ─────────────────────────────────────────────────────────────────


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_role: str
    action: str
    target_type: str
    target_id: uuid.UUID
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    meta: PaginationMeta


# ── Analytics ──────────────────────────────────────────────────────────────────


class AnalyticsResponse(BaseModel):
    total_tickets: int
    ai_processing: int  # tickets still waiting for AI enrichment
    by_status: dict[str, int]
    by_category: dict[str, int]
    by_priority: dict[str, int]
    scope: str  # "user" | "global" — tells the client which view this is
