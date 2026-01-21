"""Add user_configurations table.

This migration creates the user_configurations table for storing
user-specific detection and preparation engine settings.

Each user has exactly one configuration record (user_id is primary key).

Revision ID: w5x6y7z8a9b0
Revises: v4a1b2c3d4e5
Create Date: 2026-01-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'w5x6y7z8a9b0'
down_revision: Union[str, None] = 'v4a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create SafetyMode enum
    safety_mode_enum = sa.Enum('conservative', 'normal', 'aggressive', name='safetymode')
    safety_mode_enum.create(op.get_bind(), checkfirst=True)

    # Create user_configurations table
    op.create_table(
        'user_configurations',
        # Primary key is user_id (one config per user)
        sa.Column('user_id', sa.String(), nullable=False),

        # Buffer & Runway Settings
        sa.Column('obligations_buffer_amount', sa.Numeric(precision=15, scale=2), nullable=False, server_default='0'),
        sa.Column('runway_buffer_months', sa.Integer(), nullable=False, server_default='6'),

        # Late Payment Settings
        sa.Column('late_payment_threshold_days', sa.Integer(), nullable=False, server_default='7'),

        # Expense Monitoring Settings
        sa.Column('unexpected_expense_threshold_pct', sa.Numeric(precision=5, scale=2), nullable=False, server_default='20.0'),

        # Safety Mode
        sa.Column('safety_mode', safety_mode_enum, nullable=False, server_default='normal'),

        # Payroll Safety Settings
        sa.Column('payroll_check_days_before', sa.Integer(), nullable=False, server_default='7'),
        sa.Column('payroll_buffer_percent', sa.Numeric(precision=5, scale=2), nullable=False, server_default='10.0'),

        # Payment Clustering Settings
        sa.Column('payment_cluster_threshold_pct', sa.Numeric(precision=5, scale=2), nullable=False, server_default='40.0'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),

        # Primary key and foreign key
        sa.PrimaryKeyConstraint('user_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )


def downgrade() -> None:
    # Drop table
    op.drop_table('user_configurations')

    # Drop enum
    safety_mode_enum = sa.Enum('conservative', 'normal', 'aggressive', name='safetymode')
    safety_mode_enum.drop(op.get_bind(), checkfirst=True)
