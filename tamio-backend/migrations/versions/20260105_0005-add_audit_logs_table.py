"""Add audit_logs table for tracking data changes.

This migration creates the audit_logs table for comprehensive
audit trailing of all data operations in the system.

Revision ID: p2q3r4s5t6u7
Revises: o1p2q3r4s5t6
Create Date: 2026-01-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'p2q3r4s5t6u7'
down_revision: Union[str, None] = 'o1p2q3r4s5t6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(), nullable=False),
        # What changed
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('field_name', sa.String(), nullable=True),
        # Values
        sa.Column('old_value', JSONB, nullable=True),
        sa.Column('new_value', JSONB, nullable=True),
        # Who/what
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('source', sa.String(), nullable=False, server_default='api'),
        # Context
        sa.Column('metadata', JSONB, nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        # When
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # Primary Key
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for common queries
    op.create_index('ix_audit_log_entity_type', 'audit_logs', ['entity_type'])
    op.create_index('ix_audit_log_entity_id', 'audit_logs', ['entity_id'])
    op.create_index('ix_audit_log_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_log_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_log_created_at', 'audit_logs', ['created_at'])
    op.create_index('ix_audit_log_entity', 'audit_logs', ['entity_type', 'entity_id'])
    op.create_index('ix_audit_log_entity_action', 'audit_logs', ['entity_type', 'action'])
    op.create_index('ix_audit_log_user_time', 'audit_logs', ['user_id', 'created_at'])
    op.create_index('ix_audit_log_source', 'audit_logs', ['source'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_audit_log_source', table_name='audit_logs')
    op.drop_index('ix_audit_log_user_time', table_name='audit_logs')
    op.drop_index('ix_audit_log_entity_action', table_name='audit_logs')
    op.drop_index('ix_audit_log_entity', table_name='audit_logs')
    op.drop_index('ix_audit_log_created_at', table_name='audit_logs')
    op.drop_index('ix_audit_log_user_id', table_name='audit_logs')
    op.drop_index('ix_audit_log_action', table_name='audit_logs')
    op.drop_index('ix_audit_log_entity_id', table_name='audit_logs')
    op.drop_index('ix_audit_log_entity_type', table_name='audit_logs')
    # Drop table
    op.drop_table('audit_logs')
