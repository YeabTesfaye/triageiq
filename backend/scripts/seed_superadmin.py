"""
Superadmin seeding script — run once during initial deployment.
SUPERADMIN cannot be created via API by design; this is the only path.

Usage:
    uv run python scripts/seed_superadmin.py \
        --email admin@company.com \
        --password-file /run/secrets/admin_password \
        --name "Super Admin"

    # Or prompt interactively (no password in shell history):
    uv run python scripts/seed_superadmin.py --email admin@company.com --name "Super Admin"
"""

import argparse
import asyncio
import getpass
import json
import sys
import uuid
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


def _log(level: str, event: str, **kwargs) -> None:
    """Minimal structured JSON logger — no dependency on app logging setup."""
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
    """Avoid storing full email in audit logs."""
    local, domain = email.split("@", 1)
    return f"{local[:2]}***@{domain}"


async def _write_audit_log(
    session,
    *,
    action: AuditAction,
    target_id: uuid.UUID,
    before_state: dict,
    after_state: dict,
) -> None:
    """
    Write directly to audit_logs without going through AuditLogRepository
    so we have zero dependency on the full application stack.
    The actor_id is NULL for system-initiated actions (seed script).
    """
    log_entry = AuditLog(
        actor_id=None,  # system action — no human actor
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
    # Do not flush here — committed atomically with the user change below


async def seed_superadmin(
    email: str,
    password: str,
    full_name: str,
    *,
    dry_run: bool = False,
) -> int:
    """
    Returns 0 on success, 1 on failure.
    """
    # Normalize email (important!)
    email = email.lower().strip()

    # Validate password before touching the DB
    valid, msg = validate_password_strength(password)
    if not valid:
        _log("error", "password_policy_violation", reason=msg)
        return 1

    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with factory() as session:
            async with session.begin():  # single atomic transaction
                stmt = select(User).where(User.email == email)
                existing = (await session.execute(stmt)).scalar_one_or_none()

                # ------------------------------------------------------------------
                # EXISTING USER → UPDATE (role + password)
                # ------------------------------------------------------------------
                if existing:
                    before = {
                        "role": existing.role,
                        "status": existing.status,
                    }

                    if not dry_run:
                        existing.role = Role.SUPERADMIN.value
                        existing.status = UserStatus.ACTIVE.value

                        # 🔥 CRITICAL FIX: update password
                        existing.password_hash = hash_password(password)

                        await _write_audit_log(
                            session,
                            action=AuditAction.USER_ROLE_CHANGE,
                            target_id=existing.id,
                            before_state=before,
                            after_state={
                                "role": Role.SUPERADMIN.value,
                                "status": UserStatus.ACTIVE.value,
                                "password_updated": True,
                            },
                        )

                        _log(
                            "info",
                            "superadmin_updated",
                            email=_mask_email(email),
                            user_id=str(existing.id),
                        )
                    else:
                        _log(
                            "info",
                            "dry_run_would_update",
                            email=_mask_email(email),
                        )
                    return 0

                # ------------------------------------------------------------------
                # NEW USER → CREATE
                # ------------------------------------------------------------------
                if not dry_run:
                    user = User(
                        email=email,
                        password_hash=hash_password(password),
                        full_name=full_name,
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
                        after_state={
                            "role": Role.SUPERADMIN.value,
                            "created_by": "seed_script",
                        },
                    )

                    _log(
                        "info",
                        "superadmin_created",
                        email=_mask_email(email),
                        user_id=str(user.id),
                    )
                else:
                    _log("info", "dry_run_would_create", email=_mask_email(email))

                return 0

    except Exception as exc:
        _log("error", "seed_failed", error=str(exc), error_type=type(exc).__name__)
        return 1
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a SUPERADMIN user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Super Admin")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview what would happen without writing to DB"
    )

    # Secure password input: file path or interactive prompt
    pw_group = parser.add_mutually_exclusive_group()
    pw_group.add_argument(
        "--password-file", help="Path to file containing the password (e.g., Docker secret)"
    )
    pw_group.add_argument("--password", help="Password (avoid: visible in process list)")
    args = parser.parse_args()

    if args.password_file:
        password = Path(args.password_file).read_text().strip()
    elif args.password:
        password = args.password
    else:
        # Safest: interactive prompt, not stored in shell history
        password = getpass.getpass("Password: ")

    exit_code = asyncio.run(seed_superadmin(args.email, password, args.name, dry_run=args.dry_run))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
