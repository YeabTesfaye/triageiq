"""
Auth service unit tests — all DB and Redis interactions mocked.
Tests the business logic layer in isolation.
"""

import uuid
from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.application.services.auth_service import AuthError, AuthService
from app.domain.enums import Role, UserStatus
from app.infrastructure.security.password_handler import hash_password


def _make_mock_user(
    role=Role.USER,
    status=UserStatus.ACTIVE,
    deleted_at=None,
    failed_login_attempts=0,
    locked_until=None,
):
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.password_hash = hash_password("Test@1234")
    user.role = role.value
    user.role_enum = role
    user.status = status.value
    user.status_enum = status
    user.deleted_at = deleted_at
    user.failed_login_attempts = failed_login_attempts
    user.locked_until = locked_until
    user.is_active = deleted_at is None and status == UserStatus.ACTIVE
    user.is_locked = False
    return user


@pytest.fixture
def user_repo():
    return AsyncMock()


@pytest.fixture
def token_repo():
    return AsyncMock()


@pytest.fixture
def service(user_repo, token_repo):
    return AuthService(user_repo=user_repo, token_repo=token_repo)


# ══════════════════════════════════════════════════════════════════════════════
# REGISTER
# ══════════════════════════════════════════════════════════════════════════════
class TestRegister:
    @pytest.mark.asyncio
    async def test_register_success(self, service, user_repo):
        user_repo.email_exists.return_value = False
        created = _make_mock_user()
        user_repo.create.return_value = created

        result = await service.register(
            email="new@example.com",
            password="NewPass@99",
            full_name="New User",
        )
        assert result == created
        user_repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_register_duplicate_email_raises(self, service, user_repo):
        user_repo.email_exists.return_value = True

        with pytest.raises(AuthError) as exc:
            await service.register(
                email="existing@example.com",
                password="Test@1234",
                full_name="User",
            )
        assert exc.value.code == "EMAIL_TAKEN"

    @pytest.mark.asyncio
    async def test_register_does_not_store_plaintext_password(self, service, user_repo):
        user_repo.email_exists.return_value = False
        user_repo.create.return_value = _make_mock_user()

        await service.register(
            email="new@example.com",
            password="Test@1234",
            full_name="User",
        )

        call_kwargs = user_repo.create.call_args.kwargs
        stored_hash = call_kwargs["password_hash"]
        assert stored_hash != "Test@1234"
        assert stored_hash.startswith("$2b$")

    @pytest.mark.asyncio
    async def test_register_assigns_user_role(self, service, user_repo):
        user_repo.email_exists.return_value = False
        user_repo.create.return_value = _make_mock_user()

        await service.register(
            email="new@example.com",
            password="Test@1234",
            full_name="User",
        )

        call_kwargs = user_repo.create.call_args.kwargs
        assert call_kwargs["role"] == Role.USER


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════════════════════
class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success_returns_tokens(self, service, user_repo, token_repo):
        user = _make_mock_user()
        user_repo.get_by_email.return_value = user
        token_repo.create.return_value = MagicMock()

        with patch("app.application.services.auth_service.get_failed_login_count", return_value=0):
            with patch("app.application.services.auth_service.reset_failed_login"):
                access, refresh = await service.login(
                    email="test@example.com",
                    password="Test@1234",
                    ip_address="127.0.0.1",
                    user_agent="pytest",
                )

        assert isinstance(access, str)
        assert len(access) > 20
        assert isinstance(refresh, str)
        assert len(refresh) > 20

    @pytest.mark.asyncio
    async def test_login_wrong_password_raises(self, service, user_repo):
        user = _make_mock_user()
        user_repo.get_by_email.return_value = user

        with patch("app.application.services.auth_service.get_failed_login_count", return_value=0):
            with patch("app.application.services.auth_service.increment_failed_login"):
                with pytest.raises(AuthError) as exc:
                    await service.login(
                        email="test@example.com",
                        password="WrongPassword@1",
                        ip_address="127.0.0.1",
                        user_agent="pytest",
                    )
        assert exc.value.code == "INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_login_nonexistent_email_raises(self, service, user_repo):
        user_repo.get_by_email.return_value = None

        with patch("app.application.services.auth_service.get_failed_login_count", return_value=0):
            with patch("app.application.services.auth_service.increment_failed_login"):
                with pytest.raises(AuthError) as exc:
                    await service.login(
                        email="nobody@example.com",
                        password="Test@1234",
                        ip_address="127.0.0.1",
                        user_agent="pytest",
                    )
        assert exc.value.code == "INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_login_rate_limited(self, service, user_repo):
        with patch(
            "app.application.services.auth_service.get_failed_login_count",
            return_value=25,
        ):
            with pytest.raises(AuthError) as exc:
                await service.login(
                    email="test@example.com",
                    password="Test@1234",
                    ip_address="192.168.1.1",
                    user_agent="pytest",
                )
        assert exc.value.code == "RATE_LIMITED"

    @pytest.mark.asyncio
    async def test_login_suspended_user_raises(self, service, user_repo):
        user = _make_mock_user(status=UserStatus.SUSPENDED)
        user_repo.get_by_email.return_value = user

        with patch("app.application.services.auth_service.get_failed_login_count", return_value=0):
            with patch("app.application.services.auth_service.increment_failed_login"):
                with pytest.raises(AuthError) as exc:
                    await service.login(
                        email="test@example.com",
                        password="Test@1234",
                        ip_address="127.0.0.1",
                        user_agent="pytest",
                    )
        assert exc.value.code in ("INVALID_CREDENTIALS", "ACCOUNT_SUSPENDED")

    @pytest.mark.asyncio
    async def test_login_deleted_user_raises(self, service, user_repo):
        from datetime import datetime

        user = _make_mock_user(deleted_at=datetime.now(UTC))
        user_repo.get_by_email.return_value = user

        with patch("app.application.services.auth_service.get_failed_login_count", return_value=0):
            with patch("app.application.services.auth_service.increment_failed_login"):
                with pytest.raises(AuthError) as exc:
                    await service.login(
                        email="test@example.com",
                        password="Test@1234",
                        ip_address="127.0.0.1",
                        user_agent="pytest",
                    )
        assert exc.value.code == "INVALID_CREDENTIALS"


# ══════════════════════════════════════════════════════════════════════════════
# LOGOUT
# ══════════════════════════════════════════════════════════════════════════════
class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_blacklists_token(self, service, token_repo):
        user_id = uuid.uuid4()
        token, jti, exp = __import__(
            "app.infrastructure.security.jwt_handler", fromlist=["create_access_token"]
        ).create_access_token(str(user_id), Role.USER.value)

        with patch("app.application.services.auth_service.blacklist_access_token") as mock_bl:
            with patch("app.application.services.auth_service.decode_access_token") as mock_dec:
                payload_mock = MagicMock()
                payload_mock.jti = jti
                payload_mock.exp = exp
                mock_dec.return_value = payload_mock

                await service.logout(raw_access_token=token, user_id=user_id)

        mock_bl.assert_awaited_once()
        token_repo.revoke_all_for_user.assert_awaited_once_with(user_id)
