from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

import bleach
from pydantic import BaseModel, ConfigDict, field_validator


class SendMessageRequest(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def sanitise_and_validate_content(cls, value: str) -> str:
        cleaned = bleach.clean(value, tags=[], attributes={}, strip=True).strip()
        if len(cleaned) < 1:
            raise ValueError("Message content must not be empty.")
        if len(cleaned) > 2000:
            raise ValueError("Message content must not exceed 2000 characters.")
        return cleaned


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    sender_id: uuid.UUID | None
    sender_role: str
    content: str
    created_at: datetime


class SendMessageResponse(BaseModel):
    """Response for POST — includes user message and optional AI reply."""

    user_message: MessageResponse
    ai_reply: MessageResponse | None = None


class MessageListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: Sequence[MessageResponse]
    total: int
    limit: int
    offset: int
