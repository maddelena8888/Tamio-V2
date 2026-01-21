"""Add notification tables

Revision ID: x6y7z8a9b0c1
Revises: w5x6y7z8a9b0
Create Date: 2026-01-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "x6y7z8a9b0c1"
down_revision: Union[str, None] = "w5x6y7z8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create notification_preferences table
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column(
            "notification_type",
            sa.Enum(
                "alert_emergency",
                "alert_this_week",
                "alert_escalated",
                "action_ready",
                "action_deadline",
                "action_executed",
                "sync_completed",
                "sync_failed",
                "daily_digest",
                name="notificationtype",
            ),
            nullable=False,
        ),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, default=True),
        sa.Column("batch_into_digest", sa.Boolean(), nullable=False, default=False),
        sa.Column("quiet_hours_start", sa.Integer(), nullable=True),
        sa.Column("quiet_hours_end", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_preferences_user_type",
        "notification_preferences",
        ["user_id", "notification_type"],
        unique=True,
    )

    # Create notification_logs table
    op.create_table(
        "notification_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column(
            "notification_type",
            sa.Enum(
                "alert_emergency",
                "alert_this_week",
                "alert_escalated",
                "action_ready",
                "action_deadline",
                "action_executed",
                "sync_completed",
                "sync_failed",
                "daily_digest",
                name="notificationtype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "channel",
            sa.Enum("email", name="notificationchannel"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(), nullable=True),
        sa.Column("recipient", sa.String(), nullable=False),
        sa.Column("alert_id", sa.String(), nullable=True),
        sa.Column("action_id", sa.String(), nullable=True),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("delivered", sa.Boolean(), nullable=False, default=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["detection_alerts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["action_id"],
            ["prepared_actions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_logs_user_id",
        "notification_logs",
        ["user_id"],
    )
    op.create_index(
        "ix_notification_logs_sent_at",
        "notification_logs",
        ["sent_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_notification_logs_sent_at", table_name="notification_logs")
    op.drop_index("ix_notification_logs_user_id", table_name="notification_logs")
    op.drop_table("notification_logs")

    op.drop_index(
        "ix_notification_preferences_user_type", table_name="notification_preferences"
    )
    op.drop_table("notification_preferences")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS notificationchannel")
    op.execute("DROP TYPE IF EXISTS notificationtype")
