"""
Integration tests — full HTTP → service → repository → SQLite flows.
No mocking except Redis (which is mocked in conftest.py autouse fixture).
OpenAI is mocked per-test via the mock_openai fixture.
"""

import uuid

import pytest
from app.domain.enums import Role
from app.infrastructure.security.jwt_handler import create_access_token
from tests.conftest import make_user


# ══════════════════════════════════════════════════════════════════════════════
# AUTH FLOWS
# ══════════════════════════════════════════════════════════════════════════════
class TestAuthFlow:
    @pytest.mark.asyncio
    async def test_register_success(self, client):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"new_{uuid.uuid4().hex[:6]}@example.com",
                "password": "MySecret@99",
                "full_name": "New User",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["role"] == "user"
        assert "password" not in data
        assert "password_hash" not in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email_returns_409(self, client):
        email = f"dup_{uuid.uuid4().hex[:6]}@example.com"
        payload = {"email": email, "password": "MySecret@99", "full_name": "Dup"}
        await client.post("/api/v1/auth/register", json=payload)
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_register_weak_password_returns_422(self, client):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "weak", "full_name": "User"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_email_returns_422(self, client):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "MySecret@99", "full_name": "User"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_login_success_returns_tokens(self, client):
        email = f"login_{uuid.uuid4().hex[:6]}@example.com"
        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "MySecret@99", "full_name": "Login User"},
        )
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "MySecret@99"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password_returns_401(self, client):
        email = f"badpw_{uuid.uuid4().hex[:6]}@example.com"
        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "MySecret@99", "full_name": "User"},
        )
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "WrongPass@1"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user_returns_401(self, client):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "MySecret@99"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_authenticated(self, client):
        email = f"me_{uuid.uuid4().hex[:6]}@example.com"
        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "MySecret@99", "full_name": "Me User"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "MySecret@99"},
        )
        token = login.json()["access_token"]
        resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == email

    @pytest.mark.asyncio
    async def test_get_me_unauthenticated_returns_401(self, client):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_rotation(self, client):
        email = f"refresh_{uuid.uuid4().hex[:6]}@example.com"
        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "MySecret@99", "full_name": "Refresh User"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "MySecret@99"},
        )
        original_refresh = login.json()["refresh_token"]
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": original_refresh},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["refresh_token"] != original_refresh  # new token issued

    @pytest.mark.asyncio
    async def test_refresh_token_single_use_enforced(self, client):
        """Reusing a consumed refresh token must return 401."""
        email = f"reuse_{uuid.uuid4().hex[:6]}@example.com"
        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "MySecret@99", "full_name": "Reuse User"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "MySecret@99"},
        )
        original_refresh = login.json()["refresh_token"]
        # First use — valid
        await client.post("/api/v1/auth/refresh", json={"refresh_token": original_refresh})
        # Second use — must fail
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": original_refresh},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_jwt_signature_rejected(self, client):
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.fake.sig"},
        )
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# TICKET FLOWS
# ══════════════════════════════════════════════════════════════════════════════
class TestTicketFlow:
    @pytest.mark.asyncio
    async def test_create_ticket_ai_triage(self, client, mock_openai):
        email = f"ticket_{uuid.uuid4().hex[:6]}@example.com"
        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "MySecret@99", "full_name": "Ticket User"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "MySecret@99"},
        )
        token = login.json()["access_token"]

        resp = await client.post(
            "/api/v1/tickets",
            json={"message": "My payment failed and I cannot access premium features."},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["category"] is None
        assert data["priority"] == "high"
        assert data["status"] == "open"
        assert data["ai_response"] is not None
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_ticket_requires_auth(self, client):
        resp = await client.post(
            "/api/v1/tickets",
            json={"message": "This should fail without a token."},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_ticket_message_too_short_returns_422(self, client, mock_openai):
        email = f"short_{uuid.uuid4().hex[:6]}@example.com"
        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "MySecret@99", "full_name": "User"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "MySecret@99"},
        )
        token = login.json()["access_token"]
        resp = await client.post(
            "/api/v1/tickets",
            json={"message": "Short"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_user_cannot_see_other_users_ticket(self, client, mock_openai):
        """Ownership enforcement — 404 when accessing another user's ticket."""

        async def _register_and_login(email):
            await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "MySecret@99", "full_name": "User"},
            )
            login = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "MySecret@99"},
            )
            return login.json()["access_token"]

        token_a = await _register_and_login(f"ua_{uuid.uuid4().hex[:6]}@example.com")
        token_b = await _register_and_login(f"ub_{uuid.uuid4().hex[:6]}@example.com")

        # User A creates a ticket
        r = await client.post(
            "/api/v1/tickets",
            json={"message": "This is User A's private billing question."},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        ticket_id = r.json()["id"]

        # User B tries to read it — must get 404
        resp = await client.get(
            f"/api/v1/tickets/{ticket_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_tickets_returns_only_own(self, client, mock_openai):
        email = f"list_{uuid.uuid4().hex[:6]}@example.com"
        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "MySecret@99", "full_name": "List User"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "MySecret@99"},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create 2 tickets
        for _ in range(2):
            await client.post(
                "/api/v1/tickets",
                json={"message": "Billing question that needs urgent attention please."},
                headers=headers,
            )

        resp = await client.get("/api/v1/tickets", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN FLOWS
# ══════════════════════════════════════════════════════════════════════════════
class TestAdminFlow:
    @pytest.mark.asyncio
    async def test_regular_user_cannot_list_users(self, client):
        email = f"normal_{uuid.uuid4().hex[:6]}@example.com"
        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "MySecret@99", "full_name": "Normal"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "MySecret@99"},
        )
        token = login.json()["access_token"]
        resp = await client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_moderator_can_list_all_tickets(self, client, db_session, mock_openai):
        mod = make_user(role=Role.MODERATOR)
        db_session.add(mod)
        await db_session.flush()

        token, _, _ = create_access_token(str(mod.id), Role.MODERATOR.value)
        resp = await client.get(
            "/api/v1/admin/tickets",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "meta" in data

    @pytest.mark.asyncio
    async def test_moderator_cannot_list_users(self, client, db_session):
        mod = make_user(role=Role.MODERATOR)
        db_session.add(mod)
        await db_session.flush()

        token, _, _ = create_access_token(str(mod.id), Role.MODERATOR.value)
        resp = await client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_list_users(self, client, db_session):
        admin = make_user(role=Role.ADMIN)
        db_session.add(admin)
        await db_session.flush()

        token, _, _ = create_access_token(str(admin.id), Role.ADMIN.value)
        resp = await client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_superadmin_can_change_role(self, client, db_session):
        sa = make_user(role=Role.SUPERADMIN)
        target = make_user(role=Role.USER)
        db_session.add(sa)
        db_session.add(target)
        await db_session.flush()

        token, _, _ = create_access_token(str(sa.id), Role.SUPERADMIN.value)
        resp = await client.patch(
            f"/api/v1/admin/users/{target.id}/role",
            json={"role": "moderator"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "moderator"

    @pytest.mark.asyncio
    async def test_cannot_promote_to_superadmin_via_api(self, client, db_session):
        sa = make_user(role=Role.SUPERADMIN)
        target = make_user(role=Role.USER)
        db_session.add(sa)
        db_session.add(target)
        await db_session.flush()

        token, _, _ = create_access_token(str(sa.id), Role.SUPERADMIN.value)
        resp = await client.patch(
            f"/api/v1/admin/users/{target.id}/role",
            json={"role": "superadmin"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_cannot_change_roles(self, client, db_session):
        """Role changes require SUPERADMIN — ADMIN must get 403."""
        admin = make_user(role=Role.ADMIN)
        target = make_user(role=Role.USER)
        db_session.add(admin)
        db_session.add(target)
        await db_session.flush()

        token, _, _ = create_access_token(str(admin.id), Role.ADMIN.value)
        resp = await client.patch(
            f"/api/v1/admin/users/{target.id}/role",
            json={"role": "moderator"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_suspend_user_blocks_login(self, client, db_session):
        admin = make_user(role=Role.ADMIN)
        db_session.add(admin)
        await db_session.flush()

        # Register a regular user through the API
        email = f"suspend_{uuid.uuid4().hex[:6]}@example.com"
        reg = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "MySecret@99", "full_name": "Suspend Me"},
        )
        target_id = reg.json()["id"]

        admin_token, _, _ = create_access_token(str(admin.id), Role.ADMIN.value)
        # Suspend them
        await client.patch(
            f"/api/v1/admin/users/{target_id}/status",
            json={"status": "suspended"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Suspended user tries to log in — must fail
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "MySecret@99"},
        )
        assert login_resp.status_code == 403

    @pytest.mark.asyncio
    async def test_soft_delete_prevents_login(self, client, db_session):
        sa = make_user(role=Role.SUPERADMIN)
        db_session.add(sa)
        await db_session.flush()

        email = f"del_{uuid.uuid4().hex[:6]}@example.com"
        reg = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "MySecret@99", "full_name": "Delete Me"},
        )
        target_id = reg.json()["id"]

        sa_token, _, _ = create_access_token(str(sa.id), Role.SUPERADMIN.value)
        await client.delete(
            f"/api/v1/admin/users/{target_id}",
            headers={"Authorization": f"Bearer {sa_token}"},
        )

        # Deleted user cannot log in
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "MySecret@99"},
        )
        assert login_resp.status_code == 401

    @pytest.mark.asyncio
    async def test_audit_log_requires_superadmin(self, client, db_session):
        admin = make_user(role=Role.ADMIN)
        db_session.add(admin)
        await db_session.flush()

        token, _, _ = create_access_token(str(admin.id), Role.ADMIN.value)
        resp = await client.get(
            "/api/v1/admin/audit-logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_superadmin_can_view_audit_logs(self, client, db_session):
        sa = make_user(role=Role.SUPERADMIN)
        db_session.add(sa)
        await db_session.flush()

        token, _, _ = create_access_token(str(sa.id), Role.SUPERADMIN.value)
        resp = await client.get(
            "/api/v1/admin/audit-logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "items" in resp.json()
