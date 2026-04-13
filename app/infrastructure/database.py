"""
Database infrastructure — async engine, session factory, base model.
Uses asyncpg driver with proper connection pooling.

Changes from previous version:
  - Removed `from sqlalchemy import engine` — that import shadowed the local
    `_engine` variable name AND was being accidentally used as the bind argument
    to AsyncSessionLocal at the bottom (passing the sqlalchemy MODULE instead of
    the actual engine instance, which would crash on first use).
  - Removed the broken module-level `AsyncSessionLocal` definition.
  - Exposed `get_session_factory()` as the canonical way to get the factory.
    Import this in routers/services that need it for BackgroundTasks.
"""
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import sqlalchemy as sa
from sqlalchemy import String, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


def _json_type():
    """Use JSONB on PostgreSQL, JSON on everything else (SQLite for tests)."""
    return sa.JSON().with_variant(JSONB(), "postgresql")


class GUID(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return uuid.UUID(value) if value is not None else None


class Base(AsyncAttrs, DeclarativeBase):
    """
    Declarative base for all ORM models.
    AsyncAttrs mixin allows awaiting lazy-loaded relationships.
    """
    pass


# Engine and factory are created lazily via get_engine() / get_session_factory()
# so settings are fully loaded before the engine is configured.
_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine
    if _engine is None:
        from app.config import get_settings
        settings = get_settings()
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DB_ECHO,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_pre_ping=True,  # validate connections before checkout
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Returns the singleton async_sessionmaker.

    Use this anywhere you need to create sessions outside of the
    FastAPI request lifecycle (e.g. BackgroundTasks, CLI scripts).

    Usage in a service / background task:
        factory = get_session_factory()
        async with factory() as session:
            async with session.begin():
                ...

    expire_on_commit=False: ORM objects remain usable after session.commit()
    so you can read their attributes (e.g. message.id) after the transaction
    closes — critical for the Firebase broadcast that happens post-commit.
    """
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,  # keep attributes live after commit
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, Any]:
    """
    FastAPI dependency that yields a transactional session.
    Rolls back on any exception; always closes on exit.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def dispose_engine() -> None:
    """Called during app shutdown to cleanly release all connections."""
    if _engine is not None:
        await _engine.dispose()
