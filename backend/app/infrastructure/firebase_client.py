"""
Firebase Realtime Database client.

Initialised once via @lru_cache (mirrors redis_client.py).
All writes are non-fatal: exceptions are caught and logged, never re-raised,
so a Firebase outage cannot degrade the HTTP layer.
"""

from __future__ import annotations

import asyncio
import functools
from typing import Any

import structlog

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Lazy import guard — firebase-admin is optional at import time so the app
# can still start (and fail loudly at runtime) if the package is missing.
# ---------------------------------------------------------------------------


def _get_firebase_admin():  # pragma: no cover
    try:
        import firebase_admin  # noqa: PLC0415
        from firebase_admin import credentials, db  # noqa: PLC0415

        return firebase_admin, credentials, db
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "firebase-admin is not installed. "
            "Add it to your dependencies: pip install firebase-admin"
        ) from exc


# ---------------------------------------------------------------------------
# Singleton initialisation
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _get_firebase_app():
    """
    Initialise the Firebase Admin SDK exactly once for the process lifetime.
    Reads configuration from the application settings so the same
    pydantic-settings pattern is used everywhere.
    """
    from app.config import get_settings  # noqa: PLC0415 — avoid circular at module level

    settings = get_settings()
    firebase_admin, credentials_mod, db_mod = _get_firebase_admin()

    cred = credentials_mod.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
    app = firebase_admin.initialize_app(
        cred,
        {"databaseURL": settings.FIREBASE_DATABASE_URL},
    )
    log.info("firebase_client.initialised")
    return app, db_mod


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------


async def push_message_to_firebase(ticket_id: str, payload: dict[str, Any]) -> None:
    """
    Push *payload* to ``chats/{ticket_id}/messages`` in Firebase Realtime DB.

    This coroutine runs the blocking ``db.reference(...).push()`` call in a
    thread-pool executor so it does not stall the event loop.

    Any exception is caught, logged (without PII), and silently swallowed —
    Firebase is a broadcast bus only and must never fail an HTTP request.
    """
    try:
        _app, db_mod = _get_firebase_app()

        def _push() -> None:
            ref = db_mod.reference(f"chats/{ticket_id}/messages", app=_app)
            ref.push(payload)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _push)

        log.info("firebase_client.message_pushed", ticket_id=ticket_id)

    except Exception:  # noqa: BLE001
        # Non-fatal: log the failure but do not propagate.
        log.exception(
            "firebase_client.push_failed",
            ticket_id=ticket_id,
        )
