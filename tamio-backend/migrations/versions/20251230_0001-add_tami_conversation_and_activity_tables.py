"""Add TAMI conversation persistence and user activity tracking tables

Revision ID: e1f2a3b4c5d6
Revises: d8e9f0a1b2c3
Create Date: 2025-12-30 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = 'e1f2a3b4c5d6'
down_revision = 'd8e9f0a1b2c3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # TAMI Conversation Sessions Table
    # =========================================================================
    op.create_table(
        'tami_conversation_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('last_message_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('initial_context_snapshot', JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tami_conversation_sessions_user_id', 'tami_conversation_sessions', ['user_id'])
    op.create_index('ix_tami_conversation_sessions_is_active', 'tami_conversation_sessions', ['is_active'])

    # =========================================================================
    # TAMI Conversation Messages Table
    # =========================================================================
    op.create_table(
        'tami_conversation_messages',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('mode', sa.String(), nullable=True),
        sa.Column('ui_hints', JSONB(), nullable=True),
        sa.Column('tool_calls', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('detected_intent', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['tami_conversation_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tami_conversation_messages_session_id', 'tami_conversation_messages', ['session_id'])
    op.create_index('ix_tami_conversation_messages_created_at', 'tami_conversation_messages', ['created_at'])

    # =========================================================================
    # TAMI User Activities Table
    # =========================================================================
    op.create_table(
        'tami_user_activities',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('activity_type', sa.String(), nullable=False),
        sa.Column('context', JSONB(), nullable=True),
        sa.Column('entity_type', sa.String(), nullable=True),
        sa.Column('entity_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('conversation_session_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['conversation_session_id'], ['tami_conversation_sessions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tami_user_activities_user_id', 'tami_user_activities', ['user_id'])
    op.create_index('ix_tami_user_activities_activity_type', 'tami_user_activities', ['activity_type'])
    op.create_index('ix_tami_user_activities_created_at', 'tami_user_activities', ['created_at'])


def downgrade() -> None:
    # Drop tables in reverse order (due to foreign key constraints)
    op.drop_index('ix_tami_user_activities_created_at', table_name='tami_user_activities')
    op.drop_index('ix_tami_user_activities_activity_type', table_name='tami_user_activities')
    op.drop_index('ix_tami_user_activities_user_id', table_name='tami_user_activities')
    op.drop_table('tami_user_activities')

    op.drop_index('ix_tami_conversation_messages_created_at', table_name='tami_conversation_messages')
    op.drop_index('ix_tami_conversation_messages_session_id', table_name='tami_conversation_messages')
    op.drop_table('tami_conversation_messages')

    op.drop_index('ix_tami_conversation_sessions_is_active', table_name='tami_conversation_sessions')
    op.drop_index('ix_tami_conversation_sessions_user_id', table_name='tami_conversation_sessions')
    op.drop_table('tami_conversation_sessions')
