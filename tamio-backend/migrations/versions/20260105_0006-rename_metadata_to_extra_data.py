"""Rename metadata column to extra_data.

SQLAlchemy reserves 'metadata' as a class attribute, so we need to rename
the column to avoid conflicts when using the Declarative API.

Revision ID: q3r4s5t6u7v8
Revises: p2q3r4s5t6u7
Create Date: 2026-01-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'q3r4s5t6u7v8'
down_revision: Union[str, None] = 'p2q3r4s5t6u7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename metadata column to extra_data in integration_mappings
    op.alter_column(
        'integration_mappings',
        'metadata',
        new_column_name='extra_data'
    )

    # Rename metadata column to extra_data in integration_connections
    op.alter_column(
        'integration_connections',
        'metadata',
        new_column_name='extra_data'
    )


def downgrade() -> None:
    # Rename extra_data back to metadata in integration_mappings
    op.alter_column(
        'integration_mappings',
        'extra_data',
        new_column_name='metadata'
    )

    # Rename extra_data back to metadata in integration_connections
    op.alter_column(
        'integration_connections',
        'extra_data',
        new_column_name='metadata'
    )
