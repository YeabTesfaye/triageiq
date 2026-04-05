"""
Ticket schemas — request/response models for ticket endpoints.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import bleach
from pydantic import BaseModel, Field, field_validator

from app.domain.enums import TicketCategory, TicketPriority, TicketStatus


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
    category: Optional[str]
    priority: Optional[str]
    ai_response: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TicketListResponse(BaseModel):
    items: List[TicketResponse]
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
    ticket_id: Optional[uuid.UUID]
    error: AIErrorDetail