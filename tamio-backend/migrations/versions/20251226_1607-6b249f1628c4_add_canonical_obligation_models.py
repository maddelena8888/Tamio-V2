"""add_canonical_obligation_models

Revision ID: 6b249f1628c4
Revises: b98f42326977
Create Date: 2025-12-26 16:07:09.695769

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '6b249f1628c4'
down_revision: Union[str, None] = 'b98f42326977'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create obligation_agreements table
    op.create_table(
        'obligation_agreements',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('obligation_type', sa.String(), nullable=False),
        sa.Column('amount_type', sa.String(), nullable=False),
        sa.Column('amount_source', sa.String(), nullable=False),
        sa.Column('base_amount', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('variability_rule', JSONB, nullable=True),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column('frequency', sa.String(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('account_id', sa.String(), nullable=True),
        sa.Column('confidence', sa.String(), nullable=False),
        sa.Column('vendor_name', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('xero_contact_id', sa.String(), nullable=True),
        sa.Column('xero_invoice_id', sa.String(), nullable=True),
        sa.Column('xero_repeating_invoice_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['account_id'], ['cash_accounts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_obligation_agreements_user_id', 'obligation_agreements', ['user_id'])
    op.create_index('ix_obligation_agreements_category', 'obligation_agreements', ['category'])
    op.create_index('ix_obligation_agreements_type', 'obligation_agreements', ['obligation_type'])

    # Create obligation_schedules table
    op.create_table(
        'obligation_schedules',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('obligation_id', sa.String(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=True),
        sa.Column('period_end', sa.Date(), nullable=True),
        sa.Column('estimated_amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('estimate_source', sa.String(), nullable=False),
        sa.Column('confidence', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['obligation_id'], ['obligation_agreements.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_obligation_schedules_obligation_id', 'obligation_schedules', ['obligation_id'])
    op.create_index('ix_obligation_schedules_due_date', 'obligation_schedules', ['due_date'])
    op.create_index('ix_obligation_schedules_status', 'obligation_schedules', ['status'])

    # Create payment_events table
    op.create_table(
        'payment_events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('obligation_id', sa.String(), nullable=True),
        sa.Column('schedule_id', sa.String(), nullable=True),
        sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column('payment_date', sa.Date(), nullable=False),
        sa.Column('account_id', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('is_reconciled', sa.Boolean(), nullable=False),
        sa.Column('reconciled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('vendor_name', sa.String(), nullable=True),
        sa.Column('payment_method', sa.String(), nullable=True),
        sa.Column('reference', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('xero_payment_id', sa.String(), nullable=True),
        sa.Column('xero_bank_transaction_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['obligation_id'], ['obligation_agreements.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['schedule_id'], ['obligation_schedules.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['account_id'], ['cash_accounts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_payment_events_user_id', 'payment_events', ['user_id'])
    op.create_index('ix_payment_events_payment_date', 'payment_events', ['payment_date'])
    op.create_index('ix_payment_events_obligation_id', 'payment_events', ['obligation_id'])
    op.create_index('ix_payment_events_schedule_id', 'payment_events', ['schedule_id'])
    op.create_index('ix_payment_events_account_id', 'payment_events', ['account_id'])


def downgrade() -> None:
    # Drop tables in reverse order (to respect foreign keys)
    op.drop_index('ix_payment_events_account_id', table_name='payment_events')
    op.drop_index('ix_payment_events_schedule_id', table_name='payment_events')
    op.drop_index('ix_payment_events_obligation_id', table_name='payment_events')
    op.drop_index('ix_payment_events_payment_date', table_name='payment_events')
    op.drop_index('ix_payment_events_user_id', table_name='payment_events')
    op.drop_table('payment_events')

    op.drop_index('ix_obligation_schedules_status', table_name='obligation_schedules')
    op.drop_index('ix_obligation_schedules_due_date', table_name='obligation_schedules')
    op.drop_index('ix_obligation_schedules_obligation_id', table_name='obligation_schedules')
    op.drop_table('obligation_schedules')

    op.drop_index('ix_obligation_agreements_type', table_name='obligation_agreements')
    op.drop_index('ix_obligation_agreements_category', table_name='obligation_agreements')
    op.drop_index('ix_obligation_agreements_user_id', table_name='obligation_agreements')
    op.drop_table('obligation_agreements')
