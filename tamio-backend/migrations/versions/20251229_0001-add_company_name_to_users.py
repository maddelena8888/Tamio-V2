"""Add company_name to users table

Revision ID: c7d8e9f0a1b2
Revises: 6b249f1628c4
Create Date: 2025-12-29 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7d8e9f0a1b2'
down_revision = '6b249f1628c4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('company_name', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'company_name')
