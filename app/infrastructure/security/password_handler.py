"""
Password security — bcrypt hashing with configurable cost factor.
Uses the bcrypt library directly (avoids passlib/bcrypt4 version incompatibility).
"""

import re

import bcrypt as _bcrypt
from app.config import get_settings


def hash_password(plain: str) -> str:
    """Return a bcrypt hash. Never call with an already-hashed string."""
    rounds = get_settings().BCRYPT_ROUNDS
    salt = _bcrypt.gensalt(rounds=rounds)
    return _bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the stored bcrypt hash."""
    try:
        return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password against policy.
    Returns (is_valid, error_message).
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    return True, ""
