"""
FastAPI dependency injection layer.

This module is the RBAC enforcement point.
EVERY protected route must use these dependencies — never inline role checks.

The dependency graph:
  get_current_user
    └─ validates JWT
    └─ checks blacklist (Redis)
    └─ checks user cutoff timestamp (for suspended/banned users)
    └─ loads user from DB
    └─ raises 401/403 on any failure

  require_roles(*roles)
    └─ wraps get_current_user
    └─ raises 403 if role not in allowed set
"""

import uuid

from app.domain.entities.user import User
from app.domain.enums import Role, UserStatus
from app.infrastructure.database import AsyncSession, get_db_session
from app.infrastructure.redis_client import (
    get_user_token_cutoff,
    is_token_blacklisted,
)
from app.infrastructure.security.jwt_handler import decode_access_token
from app.repositories.user_repository import UserRepository
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer_scheme = HTTPBearer(auto_error=False)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


# ── Core Auth Dependency ───────────────────────────────────────────────────────


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """
    Validate the Bearer JWT and return the authenticated User.

    Checks performed (in order):
    1. Token present and parseable
    2. Signature and expiry valid
    3. JTI not blacklisted in Redis
    4. User exists and is not soft-deleted
    5. User not suspended or banned
    6. Token not issued before a per-user invalidation cutoff
    """
    if credentials is None:
        raise _CREDENTIALS_EXCEPTION

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise _CREDENTIALS_EXCEPTION

    # Redis blacklist check
    if await is_token_blacklisted(payload.jti):
        raise _CREDENTIALS_EXCEPTION

    # Load user
    try:
        user_id = uuid.UUID(payload.sub)
    except ValueError:
        raise _CREDENTIALS_EXCEPTION

    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)

    if user is None:
        raise _CREDENTIALS_EXCEPTION

    if user.status_enum in (UserStatus.SUSPENDED, UserStatus.BANNED):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended or banned",
        )

    # Per-user cutoff: if user was suspended/re-activated, old tokens are invalid
    cutoff = await get_user_token_cutoff(str(user_id))
    if cutoff is not None and payload.iat < cutoff:
        raise _CREDENTIALS_EXCEPTION

    # Attach request metadata for downstream logging
    request.state.user_id = str(user_id)
    request.state.user_role = user.role

    return user


async def get_current_user_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User | None:
    """Like get_current_user but returns None instead of raising for public routes."""
    if credentials is None:
        return None
    try:
        return await get_current_user(request, credentials, session)
    except HTTPException:
        return None


# ── RBAC Dependency Factory ────────────────────────────────────────────────────


def require_roles(*roles: Role):
    """
    Dependency factory that enforces role-based access control.

    Usage:
        @router.get("/admin/users")
        async def list_users(
            admin: User = Depends(require_roles(Role.ADMIN, Role.SUPERADMIN))
        ):
            ...

    Never check roles inside route handlers. Always use this factory.
    """

    async def _check(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if Role(current_user.role) not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(f"Insufficient permissions. " f"Required: {[r.value for r in roles]}"),
            )
        return current_user

    return _check


# ── Pagination ─────────────────────────────────────────────────────────────────


class PaginationParams:
    def __init__(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> None:
        self.limit = min(limit, 100)  # cap at 100 to prevent abuse
        self.offset = max(offset, 0)


# ── Request Context Helpers ────────────────────────────────────────────────────


def get_client_ip(request: Request) -> str:
    """Extract real IP, respecting X-Forwarded-For from trusted proxies."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> str:
    return request.headers.get("User-Agent", "")[:512]
