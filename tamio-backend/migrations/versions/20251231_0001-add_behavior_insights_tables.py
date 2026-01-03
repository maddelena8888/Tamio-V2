"""Add behavior insights and triggered scenarios tables

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2025-12-31 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # Behavior Metrics Table
    # Stores computed behavior metrics with statistics
    # =========================================================================
    op.create_table(
        'behavior_metrics',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('metric_type', sa.String(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=True),
        sa.Column('entity_id', sa.String(), nullable=True),

        # Current value and statistics
        sa.Column('current_value', sa.Float(), nullable=False),
        sa.Column('previous_value', sa.Float(), nullable=True),
        sa.Column('mean', sa.Float(), nullable=True),
        sa.Column('variance', sa.Float(), nullable=True),
        sa.Column('std_dev', sa.Float(), nullable=True),

        # Trend analysis
        sa.Column('trend', sa.String(), default='stable'),
        sa.Column('trend_velocity', sa.Float(), nullable=True),
        sa.Column('trend_confidence', sa.Float(), nullable=True),

        # Thresholds
        sa.Column('threshold_warning', sa.Float(), nullable=True),
        sa.Column('threshold_critical', sa.Float(), nullable=True),
        sa.Column('is_higher_better', sa.Boolean(), default=True),

        # Confidence and context
        sa.Column('data_confidence', sa.Float(), default=1.0),
        sa.Column('context_data', JSONB(), default=dict),

        # Timestamps
        sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),

        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_behavior_metrics_user_id', 'behavior_metrics', ['user_id'])
    op.create_index('ix_behavior_metrics_metric_type', 'behavior_metrics', ['metric_type'])
    op.create_index('ix_behavior_metrics_entity', 'behavior_metrics', ['entity_type', 'entity_id'])
    op.create_index('ix_behavior_metrics_computed_at', 'behavior_metrics', ['computed_at'])

    # =========================================================================
    # Behavior Triggers Table
    # Defines trigger rules for automatic scenario generation
    # =========================================================================
    op.create_table(
        'behavior_triggers',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),  # NULL = system default
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),

        # Trigger conditions (JSONB for flexible rules)
        sa.Column('conditions', JSONB(), nullable=False),

        # Scenario template to generate when triggered
        sa.Column('scenario_template', JSONB(), nullable=False),
        sa.Column('recommended_actions', JSONB(), default=list),

        # Trigger configuration
        sa.Column('severity', sa.String(), default='medium'),
        sa.Column('priority', sa.Integer(), default=50),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('cooldown_hours', sa.Integer(), default=24),
        sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),

        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_behavior_triggers_user_id', 'behavior_triggers', ['user_id'])
    op.create_index('ix_behavior_triggers_is_active', 'behavior_triggers', ['is_active'])
    op.create_index('ix_behavior_triggers_severity', 'behavior_triggers', ['severity'])

    # =========================================================================
    # Triggered Scenarios Table
    # Records scenarios generated from triggers
    # =========================================================================
    op.create_table(
        'triggered_scenarios',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('trigger_id', sa.String(), nullable=True),
        sa.Column('scenario_id', sa.String(), nullable=True),  # Links to scenarios table when created

        # Scenario details
        sa.Column('scenario_name', sa.String(), nullable=False),
        sa.Column('scenario_description', sa.Text(), nullable=True),
        sa.Column('scenario_type', sa.String(), nullable=False),
        sa.Column('scenario_parameters', JSONB(), default=dict),

        # Trigger context (what caused this)
        sa.Column('trigger_context', JSONB(), default=dict),

        # Severity and impact
        sa.Column('severity', sa.String(), default='medium'),
        sa.Column('estimated_impact', JSONB(), nullable=True),
        sa.Column('recommended_actions', JSONB(), default=list),

        # Status tracking
        sa.Column('status', sa.String(), default='pending'),
        sa.Column('user_response', sa.String(), nullable=True),
        sa.Column('response_notes', sa.Text(), nullable=True),

        # Timestamps
        sa.Column('triggered_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),

        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['trigger_id'], ['behavior_triggers.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['scenario_id'], ['scenarios.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_triggered_scenarios_user_id', 'triggered_scenarios', ['user_id'])
    op.create_index('ix_triggered_scenarios_trigger_id', 'triggered_scenarios', ['trigger_id'])
    op.create_index('ix_triggered_scenarios_status', 'triggered_scenarios', ['status'])
    op.create_index('ix_triggered_scenarios_triggered_at', 'triggered_scenarios', ['triggered_at'])

    # =========================================================================
    # Metric History Table
    # Stores historical values for trend analysis
    # =========================================================================
    op.create_table(
        'metric_history',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('metric_id', sa.String(), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('context_snapshot', JSONB(), nullable=True),

        sa.ForeignKeyConstraint(['metric_id'], ['behavior_metrics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_metric_history_metric_id', 'metric_history', ['metric_id'])
    op.create_index('ix_metric_history_recorded_at', 'metric_history', ['recorded_at'])


def downgrade() -> None:
    # Drop tables in reverse order (due to foreign key constraints)
    op.drop_index('ix_metric_history_recorded_at', table_name='metric_history')
    op.drop_index('ix_metric_history_metric_id', table_name='metric_history')
    op.drop_table('metric_history')

    op.drop_index('ix_triggered_scenarios_triggered_at', table_name='triggered_scenarios')
    op.drop_index('ix_triggered_scenarios_status', table_name='triggered_scenarios')
    op.drop_index('ix_triggered_scenarios_trigger_id', table_name='triggered_scenarios')
    op.drop_index('ix_triggered_scenarios_user_id', table_name='triggered_scenarios')
    op.drop_table('triggered_scenarios')

    op.drop_index('ix_behavior_triggers_severity', table_name='behavior_triggers')
    op.drop_index('ix_behavior_triggers_is_active', table_name='behavior_triggers')
    op.drop_index('ix_behavior_triggers_user_id', table_name='behavior_triggers')
    op.drop_table('behavior_triggers')

    op.drop_index('ix_behavior_metrics_computed_at', table_name='behavior_metrics')
    op.drop_index('ix_behavior_metrics_entity', table_name='behavior_metrics')
    op.drop_index('ix_behavior_metrics_metric_type', table_name='behavior_metrics')
    op.drop_index('ix_behavior_metrics_user_id', table_name='behavior_metrics')
    op.drop_table('behavior_metrics')
