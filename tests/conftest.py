"""
Shared pytest fixtures.
All tests use SQLite in-memory — no external services needed.
Redis and OpenAI are mocked globally so no infrastructure is required.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.entities.ticket import Ticket
from app.domain.entities.user import User
from app.domain.enums import Role, TicketCategory, TicketPriority, TicketStatus, UserStatus
from app.infrastructure.database import Base, get_db_session
from app.infrastructure.security.jwt_handler import create_access_token
from app.infrastructure.security.password_handler import hash_password
from app.main import create_app

# ── In-memory SQLite engine ────────────────────────────────────────────────────
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


# ── Mock Redis globally so every test works without Redis running ──────────────
@pytest.fixture(autouse=True)
def mock_redis_global():
    redis_mock = AsyncMock()
    redis_mock.exists.return_value = 0
    redis_mock.get.return_value = None
    redis_mock.setex.return_value = True
    redis_mock.incr.return_value = 1
    redis_mock.expire.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.ping.return_value = True
    with patch("app.infrastructure.redis_client.get_redis", return_value=redis_mock):
        yield redis_mock


# ── FastAPI test client ────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def app(db_session: AsyncSession) -> FastAPI:
    test_app = create_app()

    async def _override_db():
        yield db_session

    test_app.dependency_overrides[get_db_session] = _override_db
    return test_app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


# ── Model factories ────────────────────────────────────────────────────────────
def make_user(
    role: Role = Role.USER,
    status: UserStatus = UserStatus.ACTIVE,
    email: str | None = None,
) -> User:
    return User(
        id=uuid.uuid4(),
        email=email or f"user_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("Test@1234"),
        full_name="Test User",
        role=role.value,
        status=status.value,
        is_verified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def make_ticket(user_id: uuid.UUID | None = None) -> Ticket:
    return Ticket(
        id=uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        message="My payment failed and I cannot access premium features.",
        category=TicketCategory.BILLING.value,
        priority=TicketPriority.HIGH.value,
        ai_response="Our billing team will look into this.",
        status=TicketStatus.OPEN.value,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def auth_headers(user: User) -> dict:
    token, _, _ = create_access_token(str(user.id), user.role)
    return {"Authorization": f"Bearer {token}"}


# ── OpenAI mock fixture (opt-in) ───────────────────────────────────────────────
@pytest.fixture
def mock_openai():
    from app.infrastructure.ai.openai_client import AITicketAnalysis

    mock_analysis = AITicketAnalysis(
        category=TicketCategory.BILLING,
        priority=TicketPriority.HIGH,
        ai_response="Our billing team will look into this immediately.",
        confidence=0.95,
    )
    with patch(
        "app.infrastructure.ai.openai_client.OpenAIClient.analyze_ticket",
        new_callable=AsyncMock,
        return_value=mock_analysis,
    ):
        yield mock_analysis