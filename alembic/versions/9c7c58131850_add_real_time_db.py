"""add real time db

Revision ID: 9c7c58131850
Revises: 88c7a8443811
Create Date: 2026-04-09 14:28:59.939299

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c7c58131850'
down_revision: Union[str, Sequence[str], None] = '88c7a8443811'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
