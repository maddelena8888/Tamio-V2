"""Add OAuth states table for persistent OAuth flow

Revision ID: a1b2c3d4e5f6
Revises: z8a9b0c1d2e3
Create Date: 2026-01-27

Adds oauth_states table to persist OAuth state tokens to the database.
This fixes the issue where OAuth connections fail after server restart
because state was previously stored in-memory.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "oauth_states_001"
down_revision: Union[str, None] = "z8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create oauth_states table
    op.create_table(
        "oauth_states",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False, server_default="xero"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_oauth_states_state", "oauth_states", ["state"], unique=True)
    op.create_index("ix_oauth_states_user_id", "oauth_states", ["user_id"])
    op.create_index("ix_oauth_states_expires_at", "oauth_states", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_oauth_states_expires_at", table_name="oauth_states")
    op.drop_index("ix_oauth_states_user_id", table_name="oauth_states")
    op.drop_index("ix_oauth_states_state", table_name="oauth_states")
    op.drop_table("oauth_states")
