"""Add bi-directional sync fields to clients and expense_buckets

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2025-12-29 00:02:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = 'd8e9f0a1b2c3'
down_revision = 'c7d8e9f0a1b2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # Clients table - bi-directional sync fields
    # =========================================================================

    # Data source tracking
    op.add_column('clients', sa.Column('source', sa.String(), nullable=False, server_default='manual'))

    # Xero integration
    op.add_column('clients', sa.Column('xero_contact_id', sa.String(), nullable=True))
    op.add_column('clients', sa.Column('xero_repeating_invoice_id', sa.String(), nullable=True))

    # QuickBooks integration (future)
    op.add_column('clients', sa.Column('quickbooks_customer_id', sa.String(), nullable=True))

    # Sync state
    op.add_column('clients', sa.Column('sync_status', sa.String(), nullable=True))
    op.add_column('clients', sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('clients', sa.Column('sync_error', sa.Text(), nullable=True))

    # Field-level locking
    op.add_column('clients', sa.Column('locked_fields', JSONB(), nullable=False, server_default='[]'))

    # Create indexes for external IDs (for fast lookups during sync)
    op.create_index('ix_clients_xero_contact_id', 'clients', ['xero_contact_id'], unique=True)
    op.create_index('ix_clients_quickbooks_customer_id', 'clients', ['quickbooks_customer_id'], unique=True)

    # =========================================================================
    # Expense Buckets table - bi-directional sync fields
    # =========================================================================

    # Data source tracking
    op.add_column('expense_buckets', sa.Column('source', sa.String(), nullable=False, server_default='manual'))

    # Xero integration (suppliers)
    op.add_column('expense_buckets', sa.Column('xero_contact_id', sa.String(), nullable=True))
    op.add_column('expense_buckets', sa.Column('xero_repeating_bill_id', sa.String(), nullable=True))

    # QuickBooks integration (future)
    op.add_column('expense_buckets', sa.Column('quickbooks_vendor_id', sa.String(), nullable=True))

    # Sync state
    op.add_column('expense_buckets', sa.Column('sync_status', sa.String(), nullable=True))
    op.add_column('expense_buckets', sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('expense_buckets', sa.Column('sync_error', sa.Text(), nullable=True))

    # Field-level locking
    op.add_column('expense_buckets', sa.Column('locked_fields', JSONB(), nullable=False, server_default='[]'))

    # Create indexes for external IDs
    op.create_index('ix_expense_buckets_xero_contact_id', 'expense_buckets', ['xero_contact_id'], unique=True)
    op.create_index('ix_expense_buckets_quickbooks_vendor_id', 'expense_buckets', ['quickbooks_vendor_id'], unique=True)


def downgrade() -> None:
    # =========================================================================
    # Expense Buckets - remove sync fields
    # =========================================================================
    op.drop_index('ix_expense_buckets_quickbooks_vendor_id', table_name='expense_buckets')
    op.drop_index('ix_expense_buckets_xero_contact_id', table_name='expense_buckets')

    op.drop_column('expense_buckets', 'locked_fields')
    op.drop_column('expense_buckets', 'sync_error')
    op.drop_column('expense_buckets', 'last_synced_at')
    op.drop_column('expense_buckets', 'sync_status')
    op.drop_column('expense_buckets', 'quickbooks_vendor_id')
    op.drop_column('expense_buckets', 'xero_repeating_bill_id')
    op.drop_column('expense_buckets', 'xero_contact_id')
    op.drop_column('expense_buckets', 'source')

    # =========================================================================
    # Clients - remove sync fields
    # =========================================================================
    op.drop_index('ix_clients_quickbooks_customer_id', table_name='clients')
    op.drop_index('ix_clients_xero_contact_id', table_name='clients')

    op.drop_column('clients', 'locked_fields')
    op.drop_column('clients', 'sync_error')
    op.drop_column('clients', 'last_synced_at')
    op.drop_column('clients', 'sync_status')
    op.drop_column('clients', 'quickbooks_customer_id')
    op.drop_column('clients', 'xero_repeating_invoice_id')
    op.drop_column('clients', 'xero_contact_id')
    op.drop_column('clients', 'source')
