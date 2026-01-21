"""Add is_demo flag to users table.

Revision ID: k7l8m9n0o1p2
Revises: j6k7l8m9n0o1
Create Date: 2026-01-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'k7l8m9n0o1p2'
down_revision: Union[str, None] = 'j6k7l8m9n0o1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_demo flag to users table
    op.add_column('users', sa.Column('is_demo', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    # Remove is_demo column
    op.drop_column('users', 'is_demo')
