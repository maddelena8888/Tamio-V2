"""Add exchange_rates table.

Revision ID: j6k7l8m9n0o1
Revises: i5j6k7l8m9n0
Create Date: 2026-01-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j6k7l8m9n0o1'
down_revision: Union[str, None] = 'i5j6k7l8m9n0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create exchange_rates table
    op.create_table(
        'exchange_rates',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('from_currency', sa.String(), nullable=False),
        sa.Column('to_currency', sa.String(), nullable=False),
        sa.Column('rate', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('source', sa.String(), nullable=False, server_default='ecb'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('from_currency', 'to_currency', 'effective_date', name='uq_exchange_rate_currency_date')
    )

    # Create indexes for faster lookups
    op.create_index('ix_exchange_rates_from_currency', 'exchange_rates', ['from_currency'])
    op.create_index('ix_exchange_rates_to_currency', 'exchange_rates', ['to_currency'])
    op.create_index('ix_exchange_rates_effective_date', 'exchange_rates', ['effective_date'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_exchange_rates_effective_date', table_name='exchange_rates')
    op.drop_index('ix_exchange_rates_to_currency', table_name='exchange_rates')
    op.drop_index('ix_exchange_rates_from_currency', table_name='exchange_rates')

    # Drop table
    op.drop_table('exchange_rates')
