"""
Database infrastructure — async engine, session factory, base model.
Uses asyncpg driver with proper connection pooling.
"""

from collections.abc import AsyncGenerator
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from  sqlalchemy import TypeDecorator, String
import uuid

def _json_type():
    """Use JSONB on PostgreSQL, JSON on everything else (SQLite for tests)."""
    from sqlalchemy import event
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


# Engine is created lazily via get_engine() to allow settings injection.
_engine = None
_session_factory = None


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
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
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
