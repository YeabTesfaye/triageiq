"""
RefreshToken repository — hashed token storage, lookup, and rotation.
Raw tokens are NEVER stored; only SHA-256 hashes.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from app.config import get_settings
from app.domain.entities.audit_log import RefreshToken
from sqlalchemy import and_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession


def _hash_token(raw_token: str) -> str:
    """SHA-256 hash of a raw token for safe DB storage."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def generate_raw_token() -> str:
    """Cryptographically secure 64-byte URL-safe token."""
    return secrets.token_urlsafe(64)


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        raw_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> RefreshToken:
        settings = get_settings()
        expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        token = RefreshToken(
            user_id=user_id,
            token_hash=_hash_token(raw_token),
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_by_raw_token(self, raw_token: str) -> RefreshToken | None:
        """Look up a token by its raw value (compares against stored hash)."""
        token_hash = _hash_token(raw_token)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke(self, token_id: uuid.UUID) -> None:
        """Single-use enforcement — revoke immediately after use."""
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.id == token_id)
            .values(revoked_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> int:
        """Revoke all active tokens for a user (e.g., on suspension/ban)."""
        now = datetime.now(UTC)
        stmt = (
            update(RefreshToken)
            .where(
                and_(
                    RefreshToken.user_id == user_id,
                    RefreshToken.revoked_at.is_(None),
                    RefreshToken.expires_at > now,
                )
            )
            .values(revoked_at=now)
        )
        result = await self._session.execute(stmt)
        assert isinstance(result, CursorResult)
        return result.rowcount
