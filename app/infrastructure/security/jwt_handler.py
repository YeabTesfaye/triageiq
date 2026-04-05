"""
JWT infrastructure — token creation, validation, and blacklisting.
Tokens carry minimal payload: user_id, role, jti (for blacklisting), iat.
No PII beyond what is strictly required.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt

from app.config import get_settings


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
        self.sub = sub        # user_id (UUID str)
        self.role = role      # Role enum value
        self.jti = jti        # JWT ID — unique per token for blacklisting
        self.iat = iat        # issued-at (UNIX)
        self.exp = exp        # expiry (UNIX)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenPayload":
        return cls(
            sub=data["sub"],
            role=data["role"],
            jti=data["jti"],
            iat=data["iat"],
            exp=data["exp"],
        )

    def to_dict(self) -> Dict[str, Any]:
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
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now.timestamp() + (settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    jti = str(uuid.uuid4())

    payload = {
        "sub": user_id,
        "role": role,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expire),
        "type": "access",
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token, jti, int(expire)


def decode_access_token(token: str) -> Optional[TokenPayload]:
    """
    Decode and validate a JWT.
    Returns None (not raises) on any validation failure to allow
    consistent error handling at the dependency layer.
    """
    settings = get_settings()
    try:
        data = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if data.get("type") != "access":
            return None
        return TokenPayload.from_dict(data)
    except JWTError:
        return None


def get_token_remaining_ttl(exp_unix: int) -> int:
    """Return remaining seconds until token expiry (min 0)."""
    remaining = exp_unix - int(datetime.now(timezone.utc).timestamp())
    return max(0, remaining)