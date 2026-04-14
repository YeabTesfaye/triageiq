"""
Ticket schemas — request/response models for ticket endpoints.
"""

import uuid
from datetime import datetime

import bleach
from app.domain.entities.ticket import Ticket
from app.domain.enums import TicketStatus
from pydantic import BaseModel, Field, field_validator


class CreateTicketRequest(BaseModel):
    message: str = Field(..., min_length=10, max_length=2000)

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        """Strip all HTML tags to prevent XSS in stored content."""
        cleaned = bleach.clean(v, tags=[], strip=True).strip()
        if len(cleaned) < 10:
            raise ValueError("Message must be at least 10 characters after sanitization")
        return cleaned


class TicketResponse(BaseModel):
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


class TicketListResponse(BaseModel):
    items: list[TicketResponse]
    total: int
    limit: int
    offset: int


class UpdateTicketStatusRequest(BaseModel):
    status: TicketStatus


class AIErrorDetail(BaseModel):
    code: str
    message: str
    retry_after: int


class CreateTicketErrorResponse(BaseModel):
    """Returned when AI is unavailable but ticket may be saved in degraded mode."""

    ticket_id: uuid.UUID | None
    error: AIErrorDetail


class CreateTicketResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    message: str
    status: str
    ai_status: str  # "processing" | "completed" | "failed"
    category: str | None
    priority: str | None
    ai_response: str | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

    @classmethod
    def from_ticket(cls, ticket: "Ticket") -> "CreateTicketResponse":
        has_ai = ticket.category is not None or ticket.ai_response is not None
        return cls(
            id=ticket.id,
            user_id=ticket.user_id,
            message=ticket.message,
            status=ticket.status,
            ai_status="completed" if has_ai else "processing",
            category=ticket.category,
            priority=ticket.priority,
            ai_response=ticket.ai_response,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
        )
