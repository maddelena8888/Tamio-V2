"""Drop cash_events table - Phase 3 cleanup.

Revision ID: drop_cash_events_001
Revises: add_oauth_states_001
Create Date: 2026-01-29

This migration:
1. Drops the foreign key constraint from scenario_events.original_event_id
2. Drops the cash_events table

The forecast engine now computes events on-the-fly from ObligationSchedules,
so the cash_events table is no longer needed.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'drop_cash_events_001'
down_revision = 'oauth_states_001'
branch_labels = None
depends_on = None


def upgrade():
    # Drop foreign key constraint from scenario_events if it exists
    # We use a try/except because the constraint might not exist
    try:
        op.drop_constraint(
            'scenario_events_original_event_id_fkey',
            'scenario_events',
            type_='foreignkey'
        )
    except Exception:
        # Constraint may not exist or have a different name
        pass

    # Drop the cash_events table
    op.drop_table('cash_events')


def downgrade():
    # Recreate cash_events table
    op.create_table(
        'cash_events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('client_id', sa.String(), nullable=True),
        sa.Column('bucket_id', sa.String(), nullable=True),
        sa.Column('obligation_schedule_id', sa.String(), nullable=True),
        sa.Column('direction', sa.String(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('week_number', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('confidence', sa.String(), nullable=False),
        sa.Column('confidence_reason', sa.String(), nullable=True),
        sa.Column('is_recurring', sa.Boolean(), nullable=False, default=False),
        sa.Column('recurrence_pattern', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['bucket_id'], ['expense_buckets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['obligation_schedule_id'], ['obligation_schedules.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_cash_events_user_id', 'cash_events', ['user_id'])
    op.create_index('ix_cash_events_date', 'cash_events', ['date'])
    op.create_index('ix_cash_events_week_number', 'cash_events', ['week_number'])

    # Recreate foreign key constraint on scenario_events
    op.create_foreign_key(
        'scenario_events_original_event_id_fkey',
        'scenario_events',
        'cash_events',
        ['original_event_id'],
        ['id']
    )
