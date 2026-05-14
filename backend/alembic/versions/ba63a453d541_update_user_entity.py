"""update user entity

Revision ID: ba63a453d541
Revises: 9c7c58131850
Create Date: 2026-04-13 11:20:56.430452

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "ba63a453d541"
down_revision: str | Sequence[str] | None = "9c7c58131850"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
