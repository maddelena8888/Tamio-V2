"""add_quickbooks_integration_tables

Revision ID: g3h4i5j6k7l8
Revises: f2a3b4c5d6e7
Create Date: 2026-01-02 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'g3h4i5j6k7l8'
down_revision: Union[str, None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create quickbooks_connections table
    op.create_table(
        'quickbooks_connections',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('realm_id', sa.String(), nullable=True),  # QuickBooks company ID
        sa.Column('company_name', sa.String(), nullable=True),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('refresh_token_expires_at', sa.DateTime(timezone=True), nullable=True),  # QB refresh tokens expire in 100 days
        sa.Column('is_active', sa.Boolean(), nullable=False, default=False),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sync_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_quickbooks_connections_user_id', 'quickbooks_connections', ['user_id'], unique=True)

    # Create quickbooks_sync_logs table
    op.create_table(
        'quickbooks_sync_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('sync_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('records_fetched', JSONB(), nullable=True),
        sa.Column('records_created', JSONB(), nullable=True),
        sa.Column('records_updated', JSONB(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_quickbooks_sync_logs_user_id', 'quickbooks_sync_logs', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_quickbooks_sync_logs_user_id', table_name='quickbooks_sync_logs')
    op.drop_table('quickbooks_sync_logs')
    op.drop_index('ix_quickbooks_connections_user_id', table_name='quickbooks_connections')
    op.drop_table('quickbooks_connections')
