"""Add TAMI conversation and activity tables

Revision ID: z8a9b0c1d2e3
Revises: y7z8a9b0c1d2
Create Date: 2026-01-15

Adds tables for TAMI chat functionality:
- tami_conversation_sessions: Conversation sessions
- tami_conversation_messages: Individual messages
- tami_user_activities: User activity tracking for behavioral context
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "z8a9b0c1d2e3"
down_revision: Union[str, None] = "y7z8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create tami_conversation_sessions table
    op.create_table(
        "tami_conversation_sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("initial_context_snapshot", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_tami_conversation_sessions_user_id", "tami_conversation_sessions", ["user_id"])

    # Create tami_conversation_messages table
    op.create_table(
        "tami_conversation_messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(), nullable=True),
        sa.Column("ui_hints", postgresql.JSONB(), nullable=True),
        sa.Column("tool_calls", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("detected_intent", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["session_id"], ["tami_conversation_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_tami_conversation_messages_session_id", "tami_conversation_messages", ["session_id"])

    # Create tami_user_activities table
    op.create_table(
        "tami_user_activities",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("activity_type", sa.String(), nullable=False),
        sa.Column("context", postgresql.JSONB(), nullable=True),
        sa.Column("entity_type", sa.String(), nullable=True),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("conversation_session_id", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["conversation_session_id"],
            ["tami_conversation_sessions.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_tami_user_activities_user_id", "tami_user_activities", ["user_id"])
    op.create_index("ix_tami_user_activities_activity_type", "tami_user_activities", ["activity_type"])
    op.create_index("ix_tami_user_activities_created_at", "tami_user_activities", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_tami_user_activities_created_at", table_name="tami_user_activities")
    op.drop_index("ix_tami_user_activities_activity_type", table_name="tami_user_activities")
    op.drop_index("ix_tami_user_activities_user_id", table_name="tami_user_activities")
    op.drop_table("tami_user_activities")

    op.drop_index("ix_tami_conversation_messages_session_id", table_name="tami_conversation_messages")
    op.drop_table("tami_conversation_messages")

    op.drop_index("ix_tami_conversation_sessions_user_id", table_name="tami_conversation_sessions")
    op.drop_table("tami_conversation_sessions")
