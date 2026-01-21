"""Add integration_mappings and integration_connections tables.

This migration creates the centralized integration registry tables,
replacing scattered external ID fields (xero_contact_id, etc.) with
a unified mapping system.

Benefits:
- Single source of truth for all integration mappings
- Easy to add new integrations without schema changes
- Supports multiple mappings per entity
- Centralized sync status tracking

Revision ID: n0o1p2q3r4s5
Revises: m9n0o1p2q3r4
Create Date: 2026-01-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'n0o1p2q3r4s5'
down_revision: Union[str, None] = 'm9n0o1p2q3r4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create integration_mappings table
    op.create_table(
        'integration_mappings',
        sa.Column('id', sa.String(), nullable=False),
        # Tamio Entity Reference
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', sa.String(), nullable=False),
        # External System Reference
        sa.Column('integration_type', sa.String(), nullable=False),
        sa.Column('external_id', sa.String(), nullable=False),
        sa.Column('external_type', sa.String(), nullable=False),
        # Sync Status
        sa.Column('sync_status', sa.String(), nullable=False, server_default='synced'),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        # Metadata
        sa.Column('metadata', JSONB, nullable=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        # Primary Key
        sa.PrimaryKeyConstraint('id')
    )

    # Unique constraints for integration_mappings
    op.create_unique_constraint(
        'uq_integration_mapping_entity',
        'integration_mappings',
        ['entity_type', 'entity_id', 'integration_type']
    )
    op.create_unique_constraint(
        'uq_integration_mapping_external',
        'integration_mappings',
        ['integration_type', 'external_id', 'external_type']
    )

    # Indexes for integration_mappings
    op.create_index('ix_integration_mapping_entity_type', 'integration_mappings', ['entity_type'])
    op.create_index('ix_integration_mapping_entity_id', 'integration_mappings', ['entity_id'])
    op.create_index('ix_integration_mapping_integration_type', 'integration_mappings', ['integration_type'])
    op.create_index('ix_integration_mapping_external_id', 'integration_mappings', ['external_id'])
    op.create_index('ix_integration_mapping_entity', 'integration_mappings', ['entity_type', 'entity_id'])
    op.create_index('ix_integration_mapping_external', 'integration_mappings', ['integration_type', 'external_id'])
    op.create_index('ix_integration_mapping_status', 'integration_mappings', ['sync_status'])
    op.create_index('ix_integration_mapping_type_status', 'integration_mappings', ['integration_type', 'sync_status'])

    # Create integration_connections table
    op.create_table(
        'integration_connections',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('integration_type', sa.String(), nullable=False),
        # Connection Status
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        # OAuth Tokens
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        # Integration-specific identifiers
        sa.Column('tenant_id', sa.String(), nullable=True),
        sa.Column('realm_id', sa.String(), nullable=True),
        # Metadata
        sa.Column('metadata', JSONB, nullable=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        # Primary Key
        sa.PrimaryKeyConstraint('id')
    )

    # Unique constraint for integration_connections
    op.create_unique_constraint(
        'uq_integration_connection_user',
        'integration_connections',
        ['user_id', 'integration_type']
    )

    # Indexes for integration_connections
    op.create_index('ix_integration_connection_user', 'integration_connections', ['user_id'])
    op.create_index('ix_integration_connection_type', 'integration_connections', ['integration_type'])
    op.create_index('ix_integration_connection_status', 'integration_connections', ['status'])


def downgrade() -> None:
    # Drop integration_connections indexes and table
    op.drop_index('ix_integration_connection_status', table_name='integration_connections')
    op.drop_index('ix_integration_connection_type', table_name='integration_connections')
    op.drop_index('ix_integration_connection_user', table_name='integration_connections')
    op.drop_constraint('uq_integration_connection_user', 'integration_connections', type_='unique')
    op.drop_table('integration_connections')

    # Drop integration_mappings indexes and table
    op.drop_index('ix_integration_mapping_type_status', table_name='integration_mappings')
    op.drop_index('ix_integration_mapping_status', table_name='integration_mappings')
    op.drop_index('ix_integration_mapping_external', table_name='integration_mappings')
    op.drop_index('ix_integration_mapping_entity', table_name='integration_mappings')
    op.drop_index('ix_integration_mapping_external_id', table_name='integration_mappings')
    op.drop_index('ix_integration_mapping_integration_type', table_name='integration_mappings')
    op.drop_index('ix_integration_mapping_entity_id', table_name='integration_mappings')
    op.drop_index('ix_integration_mapping_entity_type', table_name='integration_mappings')
    op.drop_constraint('uq_integration_mapping_external', 'integration_mappings', type_='unique')
    op.drop_constraint('uq_integration_mapping_entity', 'integration_mappings', type_='unique')
    op.drop_table('integration_mappings')
