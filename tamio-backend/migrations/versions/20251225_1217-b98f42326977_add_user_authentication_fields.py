"""add_user_authentication_fields

Revision ID: b98f42326977
Revises: a1b2c3d4e5f6
Create Date: 2025-12-25 12:17:07.185975

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b98f42326977'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add authentication columns to users table
    op.add_column('users', sa.Column('hashed_password', sa.String(), nullable=True))
    op.add_column('users', sa.Column('has_completed_onboarding', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    # Remove authentication columns from users table
    op.drop_column('users', 'has_completed_onboarding')
    op.drop_column('users', 'hashed_password')
