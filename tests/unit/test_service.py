"""
Service unit tests — TicketService and AdminService business logic.
All repositories and Redis mocked.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.services.admin_service import AdminError, AdminService
from app.application.services.ticket_service import TicketService
from app.domain.enums import AuditAction, Role, TicketCategory, TicketPriority, TicketStatus, UserStatus
from app.infrastructure.ai.openai_client import AIServiceError, AITicketAnalysis


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _mock_user(role=Role.USER, user_id=None):
    u = MagicMock()
    u.id = user_id or uuid.uuid4()
    u.role = role.value
    u.role_enum = role
    u.status = UserStatus.ACTIVE.value
    u.status_enum = UserStatus.ACTIVE
    u.deleted_at = None
    u.is_active = True
    return u


def _mock_ticket(ticket_id=None, user_id=None, status=TicketStatus.OPEN):
    t = MagicMock()
    t.id = ticket_id or uuid.uuid4()
    t.user_id = user_id or uuid.uuid4()
    t.status = status.value
    t.category = TicketCategory.BILLING.value
    t.priority = TicketPriority.HIGH.value
    t.message = "My payment failed."
    return t


def _mock_ai_result():
    return AITicketAnalysis(
        category=TicketCategory.BILLING,
        priority=TicketPriority.HIGH,
        ai_response="We will help you immediately.",
        confidence=0.95,
    )


# ══════════════════════════════════════════════════════════════════════════════
# TICKET SERVICE
# ══════════════════════════════════════════════════════════════════════════════
class TestTicketService:
    @pytest.mark.asyncio
    async def test_create_ticket_with_ai_enrichment(self):
        ticket_repo = AsyncMock()
        ticket = _mock_ticket()
        ticket_repo.create.return_value = ticket

        with patch(
            "app.infrastructure.ai.openai_client.OpenAIClient.analyze_ticket",
            new_callable=AsyncMock,
            return_value=_mock_ai_result(),
        ):
            service = TicketService(ticket_repo=ticket_repo)
            await service.create_ticket(
                user_id=uuid.uuid4(),
                message="My payment failed and I need help urgently.",
            )

        ticket_repo.create.assert_awaited_once()
        call_kwargs = ticket_repo.create.call_args.kwargs
        assert call_kwargs["category"] == TicketCategory.BILLING
        assert call_kwargs["priority"] == TicketPriority.HIGH
        assert call_kwargs["ai_response"] is not None

    @pytest.mark.asyncio
    async def test_create_ticket_ai_failure_saves_degraded(self):
        """When AI is down, ticket is saved without category/priority."""
        ticket_repo = AsyncMock()
        ticket_repo.create.return_value = _mock_ticket()

        with patch(
            "app.infrastructure.ai.openai_client.OpenAIClient.analyze_ticket",
            new_callable=AsyncMock,
            side_effect=AIServiceError("OpenAI is down"),
        ):
            service = TicketService(ticket_repo=ticket_repo)
            with pytest.raises(AIServiceError):
                await service.create_ticket(
                    user_id=uuid.uuid4(),
                    message="My payment failed and I need help urgently.",
                )

        # Ticket must still have been saved even though AI failed
        ticket_repo.create.assert_awaited_once()
        call_kwargs = ticket_repo.create.call_args.kwargs
        assert call_kwargs["category"] is None
        assert call_kwargs["priority"] is None

    @pytest.mark.asyncio
    async def test_get_ticket_enforces_ownership(self):
        ticket_repo = AsyncMock()
        ticket_repo.get_by_id_and_user.return_value = None  # wrong owner
        service = TicketService(ticket_repo=ticket_repo)
        result = await service.get_ticket_for_owner(
            ticket_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_get_own_ticket_returns_it(self):
        ticket_repo = AsyncMock()
        t = _mock_ticket()
        ticket_repo.get_by_id_and_user.return_value = t
        service = TicketService(ticket_repo=ticket_repo)
        result = await service.get_ticket_for_owner(
            ticket_id=t.id,
            user_id=t.user_id,
        )
        assert result == t

    @pytest.mark.asyncio
    async def test_list_user_tickets_paginated(self):
        ticket_repo = AsyncMock()
        tickets = [_mock_ticket() for _ in range(5)]
        ticket_repo.list_by_user.return_value = (tickets, 5)
        service = TicketService(ticket_repo=ticket_repo)
        results, total = await service.get_user_tickets(
            user_id=uuid.uuid4(),
            limit=10,
            offset=0,
        )
        assert total == 5
        assert len(results) == 5


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN SERVICE
# ══════════════════════════════════════════════════════════════════════════════
class TestAdminService:
    def _make_service(self, user_repo=None, ticket_repo=None, token_repo=None, audit_repo=None):
        return AdminService(
            user_repo=user_repo or AsyncMock(),
            ticket_repo=ticket_repo or AsyncMock(),
            token_repo=token_repo or AsyncMock(),
            audit_repo=audit_repo or AsyncMock(),
        )

    # ── Role Changes ──────────────────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_change_role_cannot_promote_to_superadmin(self):
        service = self._make_service()
        actor = _mock_user(role=Role.SUPERADMIN)
        with pytest.raises(AdminError) as exc:
            await service.change_user_role(
                actor=actor,
                target_user_id=uuid.uuid4(),
                new_role=Role.SUPERADMIN,
                ip_address="127.0.0.1",
                user_agent="test",
            )
        assert exc.value.code == "FORBIDDEN_ROLE"

    @pytest.mark.asyncio
    async def test_change_role_cannot_demote_superadmin(self):
        user_repo = AsyncMock()
        target = _mock_user(role=Role.SUPERADMIN)
        user_repo.get_by_id.return_value = target
        service = self._make_service(user_repo=user_repo)
        actor = _mock_user(role=Role.SUPERADMIN)
        with pytest.raises(AdminError) as exc:
            await service.change_user_role(
                actor=actor,
                target_user_id=target.id,
                new_role=Role.ADMIN,
                ip_address="127.0.0.1",
                user_agent="test",
            )
        assert exc.value.code == "FORBIDDEN_TARGET"

    @pytest.mark.asyncio
    async def test_change_role_cannot_modify_self(self):
        user_repo = AsyncMock()
        actor = _mock_user(role=Role.SUPERADMIN)
        # target is the same person
        target = MagicMock()
        target.id = actor.id
        target.role = Role.ADMIN.value
        target.role_enum = Role.ADMIN
        user_repo.get_by_id.return_value = target
        service = self._make_service(user_repo=user_repo)
        with pytest.raises(AdminError) as exc:
            await service.change_user_role(
                actor=actor,
                target_user_id=actor.id,
                new_role=Role.USER,
                ip_address="127.0.0.1",
                user_agent="test",
            )
        assert exc.value.code == "SELF_MODIFY"

    @pytest.mark.asyncio
    async def test_change_role_writes_audit_log(self):
        user_repo = AsyncMock()
        audit_repo = AsyncMock()
        actor = _mock_user(role=Role.SUPERADMIN)
        target = _mock_user(role=Role.USER)
        user_repo.get_by_id.return_value = target
        updated = _mock_user(role=Role.ADMIN, user_id=target.id)
        user_repo.update_role.return_value = updated
        service = self._make_service(user_repo=user_repo, audit_repo=audit_repo)
        await service.change_user_role(
            actor=actor,
            target_user_id=target.id,
            new_role=Role.ADMIN,
            ip_address="10.0.0.1",
            user_agent="admin-panel",
        )
        audit_repo.create.assert_awaited_once()
        audit_kwargs = audit_repo.create.call_args.kwargs
        assert audit_kwargs["action"] == AuditAction.USER_ROLE_CHANGE
        assert audit_kwargs["actor_id"] == actor.id
        assert audit_kwargs["target_id"] == target.id

    # ── Delete User ───────────────────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_delete_user_cannot_delete_self(self):
        service = self._make_service()
        actor = _mock_user(role=Role.SUPERADMIN)
        with pytest.raises(AdminError) as exc:
            await service.delete_user(
                actor=actor,
                target_user_id=actor.id,  # same ID
                ip_address="127.0.0.1",
                user_agent="test",
            )
        assert exc.value.code == "SELF_DELETE"

    @pytest.mark.asyncio
    async def test_delete_user_cannot_delete_superadmin(self):
        user_repo = AsyncMock()
        target = _mock_user(role=Role.SUPERADMIN)
        user_repo.get_by_id.return_value = target
        service = self._make_service(user_repo=user_repo)
        actor = _mock_user(role=Role.SUPERADMIN)
        with pytest.raises(AdminError) as exc:
            await service.delete_user(
                actor=actor,
                target_user_id=target.id,
                ip_address="127.0.0.1",
                user_agent="test",
            )
        assert exc.value.code == "FORBIDDEN_TARGET"

    @pytest.mark.asyncio
    async def test_delete_user_not_found_raises(self):
        user_repo = AsyncMock()
        user_repo.get_by_id.return_value = None
        service = self._make_service(user_repo=user_repo)
        actor = _mock_user(role=Role.SUPERADMIN)
        with pytest.raises(AdminError) as exc:
            await service.delete_user(
                actor=actor,
                target_user_id=uuid.uuid4(),
                ip_address="127.0.0.1",
                user_agent="test",
            )
        assert exc.value.code == "USER_NOT_FOUND"

    # ── Suspend User ──────────────────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_suspend_user_revokes_tokens(self):
        user_repo = AsyncMock()
        token_repo = AsyncMock()
        audit_repo = AsyncMock()
        actor = _mock_user(role=Role.ADMIN)
        target = _mock_user(role=Role.USER)
        user_repo.get_by_id.return_value = target
        user_repo.update_status.return_value = target

        with patch(
            "app.application.services.admin_service.blacklist_all_user_tokens"
        ) as mock_blacklist:
            service = self._make_service(
                user_repo=user_repo, token_repo=token_repo, audit_repo=audit_repo
            )
            await service.change_user_status(
                actor=actor,
                target_user_id=target.id,
                new_status=UserStatus.SUSPENDED,
                ip_address="127.0.0.1",
                user_agent="test",
            )

        token_repo.revoke_all_for_user.assert_awaited_once_with(target.id)
        mock_blacklist.assert_awaited_once()