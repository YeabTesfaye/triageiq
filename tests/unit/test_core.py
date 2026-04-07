"""
Unit tests — pure logic with no external services.
Password hashing, JWT lifecycle, RBAC rules, AI schema validation.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.enums import Role, TicketCategory, TicketPriority, UserStatus
from app.infrastructure.security.jwt_handler import (
    create_access_token,
    decode_access_token,
    get_token_remaining_ttl,
)
from app.infrastructure.security.password_handler import (
    hash_password,
    validate_password_strength,
    verify_password,
)


# ══════════════════════════════════════════════════════════════════════════════
# PASSWORD HASHING
# ══════════════════════════════════════════════════════════════════════════════
class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        hashed = hash_password("MySecret@99")
        assert hashed != "MySecret@99"
        assert hashed.startswith("$2b$")

    def test_verify_correct_password(self):
        hashed = hash_password("MySecret@99")
        assert verify_password("MySecret@99", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("MySecret@99")
        assert verify_password("WrongPass@1", hashed) is False

    def test_same_password_different_hashes(self):
        # bcrypt uses a random salt every time
        assert hash_password("MySecret@99") != hash_password("MySecret@99")

    def test_wrong_type_does_not_crash(self):
        hashed = hash_password("MySecret@99")
        assert verify_password("anything", "not_a_valid_hash") is False


# ══════════════════════════════════════════════════════════════════════════════
# PASSWORD POLICY
# ══════════════════════════════════════════════════════════════════════════════
class TestPasswordPolicy:
    def test_too_short(self):
        ok, msg = validate_password_strength("Ab@1")
        assert ok is False
        assert "8 characters" in msg

    def test_no_uppercase(self):
        ok, msg = validate_password_strength("mysecret@99")
        assert ok is False
        assert "uppercase" in msg

    def test_no_digit(self):
        ok, msg = validate_password_strength("MySecret@abc")
        assert ok is False
        assert "digit" in msg

    def test_no_special_char(self):
        ok, msg = validate_password_strength("MySecret99")
        assert ok is False
        assert "special" in msg

    def test_valid_password(self):
        ok, msg = validate_password_strength("MySecret@99")
        assert ok is True
        assert msg == ""

    def test_minimum_length_exactly_8(self):
        ok, _ = validate_password_strength("Ab@1cde2")
        assert ok is True


# ══════════════════════════════════════════════════════════════════════════════
# JWT TOKENS
# ══════════════════════════════════════════════════════════════════════════════
class TestJWTHandler:
    def test_create_and_decode(self):
        user_id = str(uuid.uuid4())
        token, jti, exp = create_access_token(user_id, Role.USER.value)

        payload = decode_access_token(token)
        assert payload is not None
        assert payload.sub == user_id
        assert payload.role == Role.USER.value
        assert payload.jti == jti

    def test_invalid_token_returns_none(self):
        assert decode_access_token("this.is.garbage") is None

    def test_tampered_token_returns_none(self):
        token, _, _ = create_access_token(str(uuid.uuid4()), Role.USER.value)
        assert decode_access_token(token[:-5] + "XXXXX") is None

    def test_token_contains_no_pii(self):
        token, _, _ = create_access_token(str(uuid.uuid4()), Role.ADMIN.value)
        payload = decode_access_token(token)
        assert payload is not None
        d = payload.to_dict()
        assert "email" not in d
        assert "password" not in d
        assert "full_name" not in d

    def test_ttl_future_token(self):
        future = int((datetime.now(timezone.utc) + timedelta(minutes=10)).timestamp())
        ttl = get_token_remaining_ttl(future)
        assert 0 < ttl <= 600

    def test_ttl_expired_token(self):
        past = int((datetime.now(timezone.utc) - timedelta(minutes=5)).timestamp())
        assert get_token_remaining_ttl(past) == 0

    def test_each_token_has_unique_jti(self):
        uid = str(uuid.uuid4())
        _, jti1, _ = create_access_token(uid, Role.USER.value)
        _, jti2, _ = create_access_token(uid, Role.USER.value)
        assert jti1 != jti2


# ══════════════════════════════════════════════════════════════════════════════
# RBAC / ROLE HIERARCHY
# ══════════════════════════════════════════════════════════════════════════════
class TestRoleHierarchy:
    def test_privilege_levels_ascending(self):
        assert Role.USER.privilege_level < Role.MODERATOR.privilege_level
        assert Role.MODERATOR.privilege_level < Role.ADMIN.privilege_level
        assert Role.ADMIN.privilege_level < Role.SUPERADMIN.privilege_level

    def test_superadmin_outranks_all(self):
        for role in [Role.USER, Role.MODERATOR, Role.ADMIN]:
            assert Role.SUPERADMIN.outranks(role)

    def test_user_outranks_nobody(self):
        for role in [Role.MODERATOR, Role.ADMIN, Role.SUPERADMIN]:
            assert not Role.USER.outranks(role)

    def test_cannot_promote_to_superadmin_via_api(self):
        assert Role.SUPERADMIN.can_promote_to(Role.SUPERADMIN) is False

    def test_can_promote_to_admin(self):
        assert Role.SUPERADMIN.can_promote_to(Role.ADMIN) is True

    def test_can_promote_to_moderator(self):
        assert Role.SUPERADMIN.can_promote_to(Role.MODERATOR) is True


# ══════════════════════════════════════════════════════════════════════════════
# TOKEN BLACKLIST (Redis mock)
# ══════════════════════════════════════════════════════════════════════════════
class TestTokenBlacklist:
    @pytest.mark.asyncio
    async def test_blacklisted_jti_is_rejected(self):
        from app.infrastructure.redis_client import (
            blacklist_access_token,
            is_token_blacklisted,
        )

        jti = str(uuid.uuid4())
        with patch(
            "app.infrastructure.redis_client.get_redis",
        ) as mock_get:
            redis_mock = AsyncMock()
            redis_mock.setex.return_value = True
            redis_mock.exists.return_value = 1  # blacklisted
            mock_get.return_value = redis_mock

            await blacklist_access_token(jti, ttl_seconds=900)
            assert await is_token_blacklisted(jti) is True

    @pytest.mark.asyncio
    async def test_clean_jti_is_not_blacklisted(self):
        from app.infrastructure.redis_client import is_token_blacklisted

        jti = str(uuid.uuid4())
        with patch("app.infrastructure.redis_client.get_redis") as mock_get:
            redis_mock = AsyncMock()
            redis_mock.exists.return_value = 0  # not blacklisted
            mock_get.return_value = redis_mock

            assert await is_token_blacklisted(jti) is False


# ══════════════════════════════════════════════════════════════════════════════
# AI RESPONSE SCHEMA VALIDATION
# ══════════════════════════════════════════════════════════════════════════════
class TestAIResponseValidation:
    def test_valid_analysis_parsed_correctly(self):
        from app.infrastructure.ai.openai_client import AITicketAnalysis

        a = AITicketAnalysis.model_validate(
            {
                "category": "billing",
                "priority": "high",
                "ai_response": "We will help you.",
                "confidence": 0.95,
            }
        )
        assert a.category == TicketCategory.BILLING
        assert a.priority == TicketPriority.HIGH
        assert 0.0 <= a.confidence <= 1.0

    def test_invalid_category_raises(self):
        from pydantic import ValidationError
        from app.infrastructure.ai.openai_client import AITicketAnalysis

        with pytest.raises(ValidationError):
            AITicketAnalysis.model_validate(
                {
                    "category": "refund",  # not a valid category
                    "priority": "high",
                    "ai_response": "Response.",
                    "confidence": 0.9,
                }
            )

    def test_invalid_priority_raises(self):
        from pydantic import ValidationError
        from app.infrastructure.ai.openai_client import AITicketAnalysis

        with pytest.raises(ValidationError):
            AITicketAnalysis.model_validate(
                {
                    "category": "billing",
                    "priority": "urgent",  # not a valid priority
                    "ai_response": "Response.",
                    "confidence": 0.9,
                }
            )

    def test_all_categories_valid(self):
        from app.infrastructure.ai.openai_client import AITicketAnalysis

        for cat in ["billing", "technical", "general"]:
            a = AITicketAnalysis.model_validate(
                {
                    "category": cat,
                    "priority": "low",
                    "ai_response": "Response.",
                    "confidence": 0.5,
                }
            )
            assert a.category.value == cat

    def test_all_priorities_valid(self):
        from app.infrastructure.ai.openai_client import AITicketAnalysis

        for pri in ["low", "medium", "high"]:
            a = AITicketAnalysis.model_validate(
                {
                    "category": "general",
                    "priority": pri,
                    "ai_response": "Response.",
                    "confidence": 0.5,
                }
            )
            assert a.priority.value == pri