"""
User entity — SQLAlchemy ORM model with domain invariants.
The model owns its own field-level constraints.
"""

import uuid
from datetime import UTC, datetime

from app.domain.enums import Role, UserStatus
from app.infrastructure.database import  Base
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Boolean, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_role", "role"),
        Index("ix_users_status", "status"),
        Index("ix_users_deleted_at", "deleted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=Role.USER.value,
        server_default=Role.USER.value,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=UserStatus.ACTIVE.value,
        server_default=UserStatus.ACTIVE.value,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Login tracking
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    tickets: Mapped[list["Ticket"]] = relationship(  # type: ignore[name-defined]
        "Ticket", back_populates="user", lazy="selectin"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(  # type: ignore[name-defined]
        "RefreshToken", back_populates="user", lazy="noload"
    )

    # ── Domain helpers ─────────────────────────────────────────────────────────

    @property
    def role_enum(self) -> Role:
        return Role(self.role)

    @property
    def status_enum(self) -> UserStatus:
        return UserStatus(self.status)

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE.value and self.deleted_at is None

    @property
    def is_locked(self) -> bool:
        if self.locked_until is None:
            return False
        return datetime.now(UTC) < self.locked_until

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email=***{self.email[-6:]} role={self.role}>"
