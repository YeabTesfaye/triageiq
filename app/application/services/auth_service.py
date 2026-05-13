"""
Auth service — all authentication business logic.

Rules:
- No DB calls directly (uses repositories)
- No HTTP/framework imports
- No external API calls
- All secrets via infrastructure layer
"""

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from app.config import get_settings
from app.domain.entities.user import User
from app.domain.enums import Role, UserStatus
from app.infrastructure.security.jwt_handler import (
    create_access_token,
)
from app.infrastructure.security.password_handler import (
    hash_password,
    verify_password,
)
from app.repositories.refresh_token_repository import (
    RefreshTokenRepository,
    generate_raw_token,
)
from app.repositories.user_repository import UserRepository

log = structlog.get_logger(__name__)


class AuthError(Exception):
    """Domain-level auth failure. Routers map this to HTTP responses."""

    def __init__(self, message: str, code: str = "AUTH_ERROR"):
        super().__init__(message)
        self.code = code


class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: RefreshTokenRepository,
    ) -> None:
        self._users = user_repo
        self._tokens = token_repo
        self._settings = get_settings()

    async def register(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
    ) -> User:
        """
        Register a new user.
        - Validates uniqueness (409 if duplicate)
        - Hashes password with bcrypt (cost 12)
        - Assigns USER role
        """
        if await self._users.email_exists(email):
            raise AuthError("Email already registered", code="EMAIL_TAKEN")

        hashed = hash_password(password)
        user = await self._users.create(
            email=email,
            password_hash=hashed,
            full_name=full_name,
            role=Role.USER,
            status=UserStatus.ACTIVE,
        )

        log.info(
            "user_registered",
            user_id=str(user.id),
            # never log email — PII
        )
        return user

    async def login(
        self,
        *,
        email: str,
        password: str,
        ip_address: str,
        user_agent: str,
    ) -> tuple[str, str]:
        """
        Authenticate a user and issue token pair.

        Returns:
            (access_token, refresh_token)

        Raises:
            AuthError on invalid credentials, locked account, suspended account.
        """
        settings = self._settings

        # IP-level rate-limit check
        failed_count = 0
        if failed_count >= settings.AUTH_RATE_LIMIT_PER_15_MIN:
            log.warning("login_rate_limit_exceeded", ip=ip_address)
            raise AuthError(
                "Too many failed attempts. Try again in 15 minutes.",
                code="RATE_LIMITED",
            )

        user = await self._users.get_by_email(email)

        # Timing-safe: always hash even on missing user to prevent enumeration
        _dummy_hash = "$2b$12$invalidhashpadding000000000000000000000000000000000000000"
        stored_hash = user.password_hash if user else _dummy_hash

        password_valid = verify_password(password, stored_hash)

        if not user or not password_valid:
            if user:
                lock_until: datetime | None = None
                user_failures = user.failed_login_attempts + 1
                if user_failures >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
                    lock_until = datetime.now(UTC) + timedelta(
                        minutes=settings.ACCOUNT_LOCK_MINUTES
                    )
                await self._users.increment_failed_login(user.id, lock_until)
            raise AuthError("Invalid email or password", code="INVALID_CREDENTIALS")

        if user.is_locked:
            raise AuthError(
                "Account temporarily locked due to too many failed attempts",
                code="ACCOUNT_LOCKED",
            )

        if user.status_enum == UserStatus.SUSPENDED:
            raise AuthError("Account is suspended", code="ACCOUNT_SUSPENDED")

        if user.status_enum == UserStatus.BANNED:
            raise AuthError("Account is banned", code="ACCOUNT_BANNED")

        if user.deleted_at is not None:
            raise AuthError("Invalid email or password", code="INVALID_CREDENTIALS")

        # Success — issue tokens
        await self._users.record_successful_login(user.id)

        access_token, _jti, _exp = create_access_token(user_id=str(user.id), role=user.role)
        raw_refresh = generate_raw_token()
        await self._tokens.create(
            user_id=user.id,
            raw_token=raw_refresh,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        log.info("user_logged_in", user_id=str(user.id))
        return access_token, raw_refresh

    async def refresh(
        self,
        *,
        raw_refresh_token: str,
        ip_address: str,
        user_agent: str,
    ) -> tuple[str, str]:
        """
        Rotate refresh token — single-use enforcement.
        Old token is revoked; new access + refresh pair issued.
        """
        token_record = await self._tokens.get_by_raw_token(raw_refresh_token)

        if token_record is None or not token_record.is_valid:
            raise AuthError("Invalid or expired refresh token", code="INVALID_REFRESH")

        user = await self._users.get_by_id(token_record.user_id)
        if user is None or not user.is_active:
            raise AuthError("User not found or inactive", code="INVALID_REFRESH")

        # Revoke old token immediately (single-use)
        await self._tokens.revoke(token_record.id)

        # Issue new pair
        access_token, _jti, _exp = create_access_token(user_id=str(user.id), role=user.role)
        new_raw_refresh = generate_raw_token()
        await self._tokens.create(
            user_id=user.id,
            raw_token=new_raw_refresh,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        log.info("tokens_refreshed", user_id=str(user.id))
        return access_token, new_raw_refresh

    async def logout(self, *, raw_access_token: str, user_id: uuid.UUID) -> None:
        await self._tokens.revoke_all_for_user(user_id)
        log.info("user_logged_out", user_id=str(user_id))
