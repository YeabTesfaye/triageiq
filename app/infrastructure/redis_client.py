"""
Redis infrastructure — async client for token blacklisting and rate limiting.
All keys are namespaced with a prefix to avoid collisions.
"""

import logging

import redis.asyncio as aioredis
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

_redis_client: Redis | None = None


def _prefix(key: str) -> str:
    from app.config import get_settings

    return f"{get_settings().REDIS_KEY_PREFIX}{key}"


async def get_redis() -> Redis:
    """Return the shared async Redis client. Creates it on first call."""
    global _redis_client
    if _redis_client is None:
        from app.config import get_settings

        settings = get_settings()
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


# ── Token Blacklist ────────────────────────────────────────────────────────────

BLACKLIST_PREFIX = "blacklist:access:"
USER_TOKENS_PREFIX = "blacklist:user:"


async def blacklist_access_token(jti: str, ttl_seconds: int) -> None:
    """
    Mark an access token's JTI as invalid.
    TTL = remaining lifetime of the JWT so Redis auto-expires the key.
    """
    client = await get_redis()
    key = _prefix(f"{BLACKLIST_PREFIX}{jti}")
    await client.setex(key, ttl_seconds, "1")
    logger.debug("Access token blacklisted", extra={"jti": jti[:8] + "..."})


async def is_token_blacklisted(jti: str) -> bool:
    """Return True if the token JTI is in the blacklist."""
    client = await get_redis()
    key = _prefix(f"{BLACKLIST_PREFIX}{jti}")
    return await client.exists(key) == 1


async def blacklist_all_user_tokens(user_id: str, ttl_seconds: int) -> None:
    """
    Used when a user is suspended/banned — invalidates ALL their sessions
    by storing a per-user cutoff timestamp. Any token issued before this
    timestamp will be rejected.
    """
    import time

    client = await get_redis()
    key = _prefix(f"{USER_TOKENS_PREFIX}{user_id}")
    await client.setex(key, ttl_seconds, str(int(time.time())))


async def get_user_token_cutoff(user_id: str) -> int | None:
    """Return the UNIX timestamp before which all tokens are invalid."""
    client = await get_redis()
    key = _prefix(f"{USER_TOKENS_PREFIX}{user_id}")
    value = await client.get(key)
    return int(value) if value else None


# ── Failed Login Tracking ──────────────────────────────────────────────────────

FAILED_LOGIN_PREFIX = "failed_login:"


async def increment_failed_login(ip: str) -> int:
    """Increment failed login counter for an IP. Returns new count."""
    client = await get_redis()
    key = _prefix(f"{FAILED_LOGIN_PREFIX}{ip}")
    count = await client.incr(key)
    if count == 1:
        # Set expiry only on first increment
        await client.expire(key, 15 * 60)  # 15 minutes window
    return count


async def get_failed_login_count(ip: str) -> int:
    client = await get_redis()
    key = _prefix(f"{FAILED_LOGIN_PREFIX}{ip}")
    value = await client.get(key)
    return int(value) if value else 0


async def reset_failed_login(ip: str) -> None:
    client = await get_redis()
    key = _prefix(f"{FAILED_LOGIN_PREFIX}{ip}")
    await client.delete(key)
