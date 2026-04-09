"""
Message domain entity.

Represents a single chat message scoped to a support ticket.
PostgreSQL is the source of truth; this table is the only persistent store
for message content.
"""

from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base  


class Message(Base):
    __tablename__ = "messages"

    # ------------------------------------------------------------------
    # Primary key
    # ------------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Foreign keys
    # ------------------------------------------------------------------
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Data columns
    # ------------------------------------------------------------------
    sender_role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # ------------------------------------------------------------------
    # Audit columns
    # ------------------------------------------------------------------
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Relationships  (lazy="noload" — loaded explicitly when needed)
    # ------------------------------------------------------------------
    ticket = relationship("Ticket", lazy="noload")
    sender = relationship("User", lazy="noload", foreign_keys=[sender_id])

    # ------------------------------------------------------------------
    # Indexes
    # ------------------------------------------------------------------
    __table_args__ = (
        Index("ix_messages_ticket_id", "ticket_id"),
        Index("ix_messages_created_at", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Message id={self.id} ticket_id={self.ticket_id}>"