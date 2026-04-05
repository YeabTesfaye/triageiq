"""
Admin schemas — request/response models for all admin endpoints.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.domain.enums import Role, TicketStatus, UserStatus


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
    last_login_at: Optional[datetime]
    failed_login_attempts: int
    deleted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminUserDetailResponse(AdminUserResponse):
    """Extended profile with ticket summary stats."""
    ticket_stats: Dict[str, Any] = Field(default_factory=dict)


class AdminUserListResponse(BaseModel):
    items: List[AdminUserResponse]
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
    category: Optional[str]
    priority: Optional[str]
    ai_response: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminTicketListResponse(BaseModel):
    items: List[AdminTicketResponse]
    meta: PaginationMeta


class AdminUpdateTicketStatusRequest(BaseModel):
    status: TicketStatus


# ── Audit Logs ─────────────────────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    id: uuid.UUID
    actor_id: Optional[uuid.UUID]
    actor_role: str
    action: str
    target_type: str
    target_id: uuid.UUID
    before_state: Optional[Dict[str, Any]]
    after_state: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    meta: PaginationMeta


# ── Analytics ──────────────────────────────────────────────────────────────────

class AnalyticsResponse(BaseModel):
    total_tickets: int
    by_category: Dict[str, int]
    by_priority: Dict[str, int]
    by_status: Dict[str, int]