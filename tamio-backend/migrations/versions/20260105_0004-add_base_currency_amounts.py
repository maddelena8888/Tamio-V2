"""Add base_currency_amount fields for currency normalization.

This migration adds base_currency_amount fields to enable forecasting
in a normalized currency. When a client/expense/obligation uses a
different currency than the user's base currency, the converted
amount is stored here for easy aggregation.

Revision ID: o1p2q3r4s5t6
Revises: n0o1p2q3r4s5
Create Date: 2026-01-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'o1p2q3r4s5t6'
down_revision: Union[str, None] = 'n0o1p2q3r4s5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add base_currency_amount to obligation_agreements
    # This stores the base_amount converted to user's base currency
    op.add_column(
        'obligation_agreements',
        sa.Column('base_currency_amount', sa.Numeric(precision=15, scale=2), nullable=True)
    )
    op.add_column(
        'obligation_agreements',
        sa.Column('exchange_rate_used', sa.Numeric(precision=18, scale=8), nullable=True)
    )
    op.add_column(
        'obligation_agreements',
        sa.Column('exchange_rate_date', sa.Date(), nullable=True)
    )

    # Add base_currency_amount to obligation_schedules
    # This stores the estimated_amount converted to user's base currency
    op.add_column(
        'obligation_schedules',
        sa.Column('base_currency_amount', sa.Numeric(precision=15, scale=2), nullable=True)
    )
    op.add_column(
        'obligation_schedules',
        sa.Column('exchange_rate_used', sa.Numeric(precision=18, scale=8), nullable=True)
    )

    # Add base_currency_amount to expense_buckets
    # This stores the monthly_amount converted to user's base currency
    op.add_column(
        'expense_buckets',
        sa.Column('base_currency_amount', sa.Numeric(precision=15, scale=2), nullable=True)
    )
    op.add_column(
        'expense_buckets',
        sa.Column('exchange_rate_used', sa.Numeric(precision=18, scale=8), nullable=True)
    )
    op.add_column(
        'expense_buckets',
        sa.Column('exchange_rate_date', sa.Date(), nullable=True)
    )


def downgrade() -> None:
    # Remove from expense_buckets
    op.drop_column('expense_buckets', 'exchange_rate_date')
    op.drop_column('expense_buckets', 'exchange_rate_used')
    op.drop_column('expense_buckets', 'base_currency_amount')

    # Remove from obligation_schedules
    op.drop_column('obligation_schedules', 'exchange_rate_used')
    op.drop_column('obligation_schedules', 'base_currency_amount')

    # Remove from obligation_agreements
    op.drop_column('obligation_agreements', 'exchange_rate_date')
    op.drop_column('obligation_agreements', 'exchange_rate_used')
    op.drop_column('obligation_agreements', 'base_currency_amount')
