"""sync UUID type

Revision ID: 0e088236c8d5
Revises: 7bedc6b97bb0
Create Date: 2026-04-08 08:58:06.081526
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0e088236c8d5"
down_revision: Union[str, Sequence[str], None] = "7bedc6b97bb0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Convert audit_logs.before_state → JSONB
    op.alter_column(
        "audit_logs",
        "before_state",
        existing_type=sa.UUID(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=True,
        postgresql_using="to_jsonb(before_state)",
    )

    # Convert audit_logs.after_state → JSONB
    op.alter_column(
        "audit_logs",
        "after_state",
        existing_type=sa.UUID(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=True,
        postgresql_using="to_jsonb(after_state)",
    )

    # Convert tickets.ai_raw → JSONB
    op.alter_column(
        "tickets",
        "ai_raw",
        existing_type=sa.UUID(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=True,
        postgresql_using="to_jsonb(ai_raw)",
    )


def downgrade() -> None:
    """Downgrade schema."""

    # Revert tickets.ai_raw → UUID
    op.alter_column(
        "tickets",
        "ai_raw",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.UUID(),
        existing_nullable=True,
        postgresql_using="ai_raw::text::uuid",
    )

    # Revert audit_logs.after_state → UUID
    op.alter_column(
        "audit_logs",
        "after_state",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.UUID(),
        existing_nullable=True,
        postgresql_using="after_state::text::uuid",
    )

    # Revert audit_logs.before_state → UUID
    op.alter_column(
        "audit_logs",
        "before_state",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.UUID(),
        existing_nullable=True,
        postgresql_using="before_state::text::uuid",
    )