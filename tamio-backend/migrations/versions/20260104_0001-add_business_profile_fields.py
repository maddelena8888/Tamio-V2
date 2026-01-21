"""Add business profile fields to users table.

Revision ID: i5j6k7l8m9n0
Revises: h4i5j6k7l8m9
Create Date: 2026-01-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'i5j6k7l8m9n0'
down_revision: Union[str, None] = 'h4i5j6k7l8m9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add business profile fields to users table
    op.add_column('users', sa.Column('industry', sa.String(), nullable=True))
    op.add_column('users', sa.Column('subcategory', sa.String(), nullable=True))
    op.add_column('users', sa.Column('revenue_range', sa.String(), nullable=True))
    op.add_column('users', sa.Column('business_profile_completed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Remove columns
    op.drop_column('users', 'business_profile_completed_at')
    op.drop_column('users', 'revenue_range')
    op.drop_column('users', 'subcategory')
    op.drop_column('users', 'industry')
