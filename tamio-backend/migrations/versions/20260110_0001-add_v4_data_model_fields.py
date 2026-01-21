"""Add V4 data model fields.

This migration adds fields required by the V4 architecture brief:
- Client: avg_payment_delay_days, relationship_type, revenue_percent, risk_level
- ExpenseBucket: payment_terms, payment_terms_days, flexibility_level, criticality, delay_history
- PaymentEvent: variance_vs_expected
- New table: execution_automation_rules (V2 auto-execution)

Revision ID: v4a1b2c3d4e5
Revises: q3r4s5t6u7v8
Create Date: 2026-01-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'v4a1b2c3d4e5'
down_revision: Union[str, None] = 'q3r4s5t6u7v8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================================
    # Client V4 Fields
    # ==========================================================================
    # Payment pattern: average days late
    op.add_column('clients', sa.Column(
        'avg_payment_delay_days',
        sa.Integer(),
        nullable=True,
        server_default='0'
    ))

    # Relationship type for tone adjustment in communications
    op.add_column('clients', sa.Column(
        'relationship_type',
        sa.String(),
        nullable=True
    ))

    # Revenue concentration percentage
    op.add_column('clients', sa.Column(
        'revenue_percent',
        sa.Numeric(precision=5, scale=2),
        nullable=True
    ))

    # Unified risk level
    op.add_column('clients', sa.Column(
        'risk_level',
        sa.String(),
        nullable=True
    ))

    # ==========================================================================
    # ExpenseBucket (Vendor) V4 Fields
    # ==========================================================================
    # Payment terms (Net-30, Net-60, etc.)
    op.add_column('expense_buckets', sa.Column(
        'payment_terms',
        sa.String(),
        nullable=True
    ))

    # Payment terms in days
    op.add_column('expense_buckets', sa.Column(
        'payment_terms_days',
        sa.Integer(),
        nullable=True
    ))

    # Flexibility level for payment delays
    op.add_column('expense_buckets', sa.Column(
        'flexibility_level',
        sa.String(),
        nullable=True
    ))

    # Criticality of vendor/expense
    op.add_column('expense_buckets', sa.Column(
        'criticality',
        sa.String(),
        nullable=True
    ))

    # Past delay history (JSONB array)
    op.add_column('expense_buckets', sa.Column(
        'delay_history',
        postgresql.JSONB(astext_type=sa.Text()),
        nullable=True,
        server_default='[]'
    ))

    # ==========================================================================
    # PaymentEvent V4 Fields
    # ==========================================================================
    # Variance vs expected (actual - expected)
    op.add_column('payment_events', sa.Column(
        'variance_vs_expected',
        sa.Numeric(precision=15, scale=2),
        nullable=True
    ))

    # ==========================================================================
    # ExecutionAutomationRule Table (V2 Auto-Execution)
    # ==========================================================================
    op.create_table(
        'execution_automation_rules',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('action_type', sa.String(), nullable=False),
        sa.Column('auto_execute', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('threshold_amount', sa.Float(), nullable=True),
        sa.Column('threshold_currency', sa.String(), nullable=True, server_default='USD'),
        sa.Column('excluded_tags', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('included_tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('require_approval', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_locked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create index for faster lookups by user
    op.create_index(
        'ix_execution_automation_rules_user_id',
        'execution_automation_rules',
        ['user_id']
    )

    # Create unique constraint: one rule per action type per user
    op.create_index(
        'ix_execution_automation_rules_user_action',
        'execution_automation_rules',
        ['user_id', 'action_type'],
        unique=True
    )


def downgrade() -> None:
    # Drop execution_automation_rules table
    op.drop_index('ix_execution_automation_rules_user_action', table_name='execution_automation_rules')
    op.drop_index('ix_execution_automation_rules_user_id', table_name='execution_automation_rules')
    op.drop_table('execution_automation_rules')

    # Drop PaymentEvent V4 columns
    op.drop_column('payment_events', 'variance_vs_expected')

    # Drop ExpenseBucket V4 columns
    op.drop_column('expense_buckets', 'delay_history')
    op.drop_column('expense_buckets', 'criticality')
    op.drop_column('expense_buckets', 'flexibility_level')
    op.drop_column('expense_buckets', 'payment_terms_days')
    op.drop_column('expense_buckets', 'payment_terms')

    # Drop Client V4 columns
    op.drop_column('clients', 'risk_level')
    op.drop_column('clients', 'revenue_percent')
    op.drop_column('clients', 'relationship_type')
    op.drop_column('clients', 'avg_payment_delay_days')
