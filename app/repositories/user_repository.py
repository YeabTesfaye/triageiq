"""
User repository — all database operations for the User entity.
Services MUST use this; no direct DB calls outside repositories.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from app.domain.entities.user import User
from app.domain.enums import Role, UserStatus
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import ColumnElement, true


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        full_name: str,
        role: Role = Role.USER,
        status: UserStatus = UserStatus.ACTIVE,
    ) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            role=role.value,
            status=status.value,
        )
        self._session.add(user)
        await self._session.flush()  # get ID without committing
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(and_(User.id == user_id, User.deleted_at.is_(None)))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_including_deleted(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(and_(User.email == email, User.deleted_at.is_(None)))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        stmt = select(func.count()).where(and_(User.email == email, User.deleted_at.is_(None)))
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    async def list_users(
        self,
        *,
        role: Role | None = None,
        status: UserStatus | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        include_deleted: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[User], int]:
        """Returns (users, total_count) for pagination."""
        conditions : list[ColumnElement[bool]] = []
        if not include_deleted:
            conditions.append(User.deleted_at.is_(None))
        if role:
            conditions.append(User.role == role.value)
        if status:
            conditions.append(User.status == status.value)
        if created_after:
            conditions.append(User.created_at >= created_after)
        if created_before:
            conditions.append(User.created_at <= created_before)

        where_clause = and_(*conditions) if conditions else true()  # type: ignore

        count_stmt = select(func.count()).select_from(User).where(where_clause)
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()

        stmt = (
            select(User)
            .where(where_clause)
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        users = result.scalars().all()

        return users, total

    async def update_role(self, user_id: uuid.UUID, role: Role) -> User | None:
        stmt = (
            update(User)
            .where(and_(User.id == user_id, User.deleted_at.is_(None)))
            .values(role=role.value, updated_at=datetime.now(UTC))
            .returning(User)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(self, user_id: uuid.UUID, status: UserStatus) -> User | None:
        stmt = (
            update(User)
            .where(and_(User.id == user_id, User.deleted_at.is_(None)))
            .values(status=status.value, updated_at=datetime.now(UTC))
            .returning(User)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def soft_delete(self, user_id: uuid.UUID) -> User | None:
        now = datetime.now(UTC)
        stmt = (
            update(User)
            .where(and_(User.id == user_id, User.deleted_at.is_(None)))
            .values(deleted_at=now, updated_at=now)
            .returning(User)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def record_successful_login(self, user_id: uuid.UUID) -> None:
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(
                last_login_at=datetime.now(UTC),
                failed_login_attempts=0,
                locked_until=None,
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.execute(stmt)

    async def increment_failed_login(
        self, user_id: uuid.UUID, lock_until: datetime | None = None
    ) -> None:
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(
                failed_login_attempts=User.failed_login_attempts + 1,
                locked_until=lock_until,
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.execute(stmt)
