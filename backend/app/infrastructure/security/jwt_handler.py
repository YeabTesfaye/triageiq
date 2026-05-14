"""
JWT infrastructure — token creation, validation, and blacklisting.
Tokens carry minimal payload: user_id, role, jti (for blacklisting), iat.
No PII beyond what is strictly required.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from app.config import get_settings
from jose import JWTError, jwt

log = structlog.get_logger(__name__)


class TokenPayload:
    """Strongly-typed JWT payload. Avoids raw dict access across the codebase."""

    __slots__ = ("sub", "role", "jti", "iat", "exp")

    def __init__(
        self,
        sub: str,
        role: str,
        jti: str,
        iat: int,
        exp: int,
    ) -> None:
        self.sub = sub  # user_id (UUID str)
        self.role = role  # Role enum value
        self.jti = jti  # JWT ID — unique per token for blacklisting
        self.iat = iat  # issued-at (UNIX)
        self.exp = exp  # expiry (UNIX)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TokenPayload":
        return cls(
            sub=data["sub"],
            role=data["role"],
            jti=data["jti"],
            iat=data["iat"],
            exp=data["exp"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sub": self.sub,
            "role": self.role,
            "jti": self.jti,
            "iat": self.iat,
            "exp": self.exp,
        }


def create_access_token(user_id: str, role: str) -> tuple[str, str, int]:
    """
    Create a signed JWT access token.

    Returns:
        (token, jti, exp_unix_timestamp)

    Raises:
        ValueError: if ACCESS_TOKEN_EXPIRE_MINUTES is not a positive integer —
                    catches misconfiguration at token-issue time, not at decode.
    """
    settings = get_settings()

    expire_minutes: int = settings.ACCESS_TOKEN_EXPIRE_MINUTES

    # Guard: catch zero/negative config values that would cause instant expiry
    if expire_minutes <= 0:
        raise ValueError(
            f"ACCESS_TOKEN_EXPIRE_MINUTES must be > 0, got {expire_minutes!r}. "
            "Check your .env file."
        )

    now = datetime.now(UTC)
    # Use timedelta — no manual * 60 arithmetic that can be double-applied
    expires_at: datetime = now + timedelta(minutes=expire_minutes)
    exp_unix = int(expires_at.timestamp())
    jti = str(uuid.uuid4())

    payload = {
        "sub": user_id,
        "role": role,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": exp_unix,
        "type": "access",
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    log.debug(
        "access_token_created",
        user_id=user_id,
        jti=jti,
        expire_minutes=expire_minutes,
        expires_at=expires_at.isoformat(),
    )

    return token, jti, exp_unix


def decode_access_token(token: str) -> TokenPayload | None:
    """
    Decode and validate a JWT.
    Returns None (not raises) on any validation failure — consistent
    error handling lives at the dependency layer, not here.
    """
    settings = get_settings()
    try:
        data = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if data.get("type") != "access":
            log.warning("jwt_wrong_type", token_type=data.get("type"))
            return None
        return TokenPayload.from_dict(data)
    except JWTError as exc:
        log.debug("jwt_decode_failed", reason=str(exc))
        return None


def get_token_remaining_ttl(exp_unix: int) -> int:
    """Return remaining seconds until token expiry (floor 0)."""
    remaining = exp_unix - int(datetime.now(UTC).timestamp())
    return max(0, remaining)
