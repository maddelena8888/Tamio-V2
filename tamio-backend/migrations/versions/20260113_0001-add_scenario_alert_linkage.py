"""Add scenario to alert linkage fields

Revision ID: y7z8a9b0c1d2
Revises: x6y7z8a9b0c1
Create Date: 2026-01-13

Links scenarios to detection alerts so that suggested scenarios can be
derived from active alerts (e.g., a late payment alert generates a
payment delay scenario suggestion).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "y7z8a9b0c1d2"
down_revision: Union[str, None] = "x6y7z8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add source_alert_id column to scenarios table
    op.add_column(
        "scenarios",
        sa.Column("source_alert_id", sa.String(), nullable=True),
    )

    # Add source_detection_type column to scenarios table
    op.add_column(
        "scenarios",
        sa.Column("source_detection_type", sa.String(), nullable=True),
    )

    # Add foreign key constraint for source_alert_id
    op.create_foreign_key(
        "fk_scenarios_source_alert_id",
        "scenarios",
        "detection_alerts",
        ["source_alert_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Create index for efficient lookups of scenarios by alert
    op.create_index(
        "ix_scenarios_source_alert_id",
        "scenarios",
        ["source_alert_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_scenarios_source_alert_id", table_name="scenarios")
    op.drop_constraint("fk_scenarios_source_alert_id", "scenarios", type_="foreignkey")
    op.drop_column("scenarios", "source_detection_type")
    op.drop_column("scenarios", "source_alert_id")