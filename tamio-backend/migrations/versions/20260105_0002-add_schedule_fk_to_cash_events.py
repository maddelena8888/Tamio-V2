"""Add obligation_schedule_id FK to cash_events table.

This migration enables traceability from CashEvents back to the
ObligationSchedule that generated them, supporting:
- Full audit trail from forecast events back to obligations
- Deduplication of events when regenerating schedules
- Reconciliation between scheduled and actual payments

Revision ID: m9n0o1p2q3r4
Revises: l8m9n0o1p2q3
Create Date: 2026-01-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'm9n0o1p2q3r4'
down_revision: Union[str, None] = 'l8m9n0o1p2q3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add obligation_schedule_id FK to cash_events
    # This links generated CashEvents back to their source schedule
    op.add_column(
        'cash_events',
        sa.Column('obligation_schedule_id', sa.String(), nullable=True)
    )
    op.create_foreign_key(
        'fk_cash_events_schedule_id',
        'cash_events',
        'obligation_schedules',
        ['obligation_schedule_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index(
        'ix_cash_events_schedule_id',
        'cash_events',
        ['obligation_schedule_id']
    )


def downgrade() -> None:
    # Remove obligation_schedule_id FK and column
    op.drop_index('ix_cash_events_schedule_id', table_name='cash_events')
    op.drop_constraint('fk_cash_events_schedule_id', 'cash_events', type_='foreignkey')
    op.drop_column('cash_events', 'obligation_schedule_id')
