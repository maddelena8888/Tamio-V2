"""add_scenario_analysis_tables

Revision ID: 766411b5d7ae
Revises: 4ab426e10f89
Create Date: 2025-12-23 20:35:31.303787

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '766411b5d7ae'
down_revision: Union[str, None] = '4ab426e10f89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create financial_rules table
    op.create_table(
        'financial_rules',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('rule_type', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('threshold_config', sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('evaluation_scope', sa.String(), default='all'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create scenarios table
    op.create_table(
        'scenarios',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('scenario_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), default='draft'),
        sa.Column('entry_path', sa.String(), nullable=True),
        sa.Column('suggested_reason', sa.String(), nullable=True),
        sa.Column('scope_config', sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column('parameters', sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column('linked_scenarios', sa.dialects.postgresql.JSONB(), default=[]),
        sa.Column('layer_order', sa.Integer(), default=0),
        sa.Column('parent_scenario_id', sa.String(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmed_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['parent_scenario_id'], ['scenarios.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create scenario_events table
    op.create_table(
        'scenario_events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('scenario_id', sa.String(), nullable=False),
        sa.Column('original_event_id', sa.String(), nullable=True),
        sa.Column('operation', sa.String(), nullable=False),
        sa.Column('event_data', sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column('layer_attribution', sa.String(), nullable=True),
        sa.Column('change_reason', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['scenario_id'], ['scenarios.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['original_event_id'], ['cash_events.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create rule_evaluations table
    op.create_table(
        'rule_evaluations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('rule_id', sa.String(), nullable=False),
        sa.Column('scenario_id', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('is_breached', sa.Boolean(), default=False),
        sa.Column('first_breach_week', sa.Integer(), nullable=True),
        sa.Column('first_breach_date', sa.String(), nullable=True),
        sa.Column('breach_amount', sa.DECIMAL(15, 2), nullable=True),
        sa.Column('action_window_weeks', sa.Integer(), nullable=True),
        sa.Column('evaluation_details', sa.dialects.postgresql.JSONB(), default={}),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['rule_id'], ['financial_rules.id']),
        sa.ForeignKeyConstraint(['scenario_id'], ['scenarios.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create scenario_forecasts table
    op.create_table(
        'scenario_forecasts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('scenario_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('forecast_data', sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column('delta_data', sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column('summary', sa.dialects.postgresql.JSONB(), default={}),
        sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['scenario_id'], ['scenarios.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('scenario_forecasts')
    op.drop_table('rule_evaluations')
    op.drop_table('scenario_events')
    op.drop_table('scenarios')
    op.drop_table('financial_rules')
