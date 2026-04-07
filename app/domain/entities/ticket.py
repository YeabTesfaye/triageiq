"""
Ticket entity — support ticket with AI-enriched fields.
"""

import uuid
from datetime import datetime
from typing import Any

from app.domain.enums import TicketCategory, TicketPriority, TicketStatus
from app.infrastructure.database import GUID, Base, _json_type
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_user_id", "user_id"),
        Index("ix_tickets_created_at", "created_at"),
        Index("ix_tickets_status", "status"),
        Index("ix_tickets_category", "category"),
        Index("ix_tickets_priority", "priority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    message: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ai_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Full raw AI JSON payload for debugging / re-processing
    ai_raw: Mapped[dict[str, Any] | None] = mapped_column(_json_type(), nullable=True)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TicketStatus.OPEN.value,
        server_default=TicketStatus.OPEN.value,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", back_populates="tickets", lazy="noload"
    )

    @property
    def category_enum(self) -> TicketCategory | None:
        return TicketCategory(self.category) if self.category else None

    @property
    def priority_enum(self) -> TicketPriority | None:
        return TicketPriority(self.priority) if self.priority else None

    @property
    def status_enum(self) -> TicketStatus:
        return TicketStatus(self.status)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Ticket id={self.id} status={self.status} priority={self.priority}>"
