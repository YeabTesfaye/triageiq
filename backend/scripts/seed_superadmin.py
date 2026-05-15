"""
Superadmin seeding script — hardcoded credentials for local dev.
NOT FOR PRODUCTION. Do not commit this file.

Usage:
    uv run python scripts/seed_superadmin.py
"""

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.domain.entities.audit_log import AuditLog
from app.domain.entities.user import User
from app.domain.enums import AuditAction, Role, UserStatus
from app.infrastructure.security.password_handler import (
    hash_password,
    validate_password_strength,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ─── HARDCODED CREDENTIALS ────────────────────────────────────────────────────
ADMIN_EMAIL = "admin@yourcompany.com"
ADMIN_PASSWORD = "YourStrongPassword123!"
ADMIN_NAME = "Super Admin"
# ──────────────────────────────────────────────────────────────────────────────


def _log(level: str, event: str, **kwargs) -> None:
    print(
        json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": level,
                "event": event,
                **kwargs,
            }
        ),
        flush=True,
    )


def _mask_email(email: str) -> str:
    local, domain = email.split("@", 1)
    return f"{local[:2]}***@{domain}"


async def _write_audit_log(session, *, action, target_id, before_state, after_state):
    log_entry = AuditLog(
        actor_id=None,
        actor_role="system",
        action=action.value,
        target_type="user",
        target_id=target_id,
        before_state=before_state,
        after_state=after_state,
        ip_address="127.0.0.1",
        user_agent="seed_superadmin.py",
    )
    session.add(log_entry)


async def seed_superadmin() -> int:
    email = ADMIN_EMAIL.lower().strip()
    password = ADMIN_PASSWORD
    name = ADMIN_NAME

    valid, msg = validate_password_strength(password)
    if not valid:
        _log("error", "password_policy_violation", reason=msg)
        return 1

    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with factory() as session:
            async with session.begin():
                stmt = select(User).where(User.email == email)
                existing = (await session.execute(stmt)).scalar_one_or_none()

                if existing:
                    before = {"role": existing.role, "status": existing.status}
                    existing.role = Role.SUPERADMIN.value
                    existing.status = UserStatus.ACTIVE.value
                    existing.password_hash = hash_password(password)
                    await _write_audit_log(
                        session,
                        action=AuditAction.USER_ROLE_CHANGE,
                        target_id=existing.id,
                        before_state=before,
                        after_state={"role": Role.SUPERADMIN.value, "password_updated": True},
                    )
                    _log(
                        "info",
                        "superadmin_updated",
                        email=_mask_email(email),
                        user_id=str(existing.id),
                    )
                else:
                    user = User(
                        email=email,
                        password_hash=hash_password(password),
                        full_name=name,
                        role=Role.SUPERADMIN.value,
                        status=UserStatus.ACTIVE.value,
                        is_verified=True,
                    )
                    session.add(user)
                    await session.flush()
                    await _write_audit_log(
                        session,
                        action=AuditAction.USER_ROLE_CHANGE,
                        target_id=user.id,
                        before_state={},
                        after_state={"role": Role.SUPERADMIN.value, "created_by": "seed_script"},
                    )
                    _log(
                        "info", "superadmin_created", email=_mask_email(email), user_id=str(user.id)
                    )
                return 0

    except Exception as exc:
        _log("error", "seed_failed", error=str(exc), error_type=type(exc).__name__)
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    exit_code = asyncio.run(seed_superadmin())
    sys.exit(exit_code)
