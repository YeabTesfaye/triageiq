"""
Auth schemas — request/response Pydantic models for auth endpoints.
These are the API contract; never expose internal models directly.
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.infrastructure.security.password_handler import validate_password_strength


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        valid, msg = validate_password_strength(v)
        if not valid:
            raise ValueError(msg)
        return v

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserProfileResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    status: str
    is_verified: bool
    last_login_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}