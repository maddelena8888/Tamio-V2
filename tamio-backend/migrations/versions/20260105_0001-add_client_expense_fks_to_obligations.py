"""Add client_id and expense_bucket_id FKs to obligation_agreements.

This migration establishes the One-to-Many relationship between
Client/ExpenseBucket and ObligationAgreement, enabling:
- Each Client to have multiple ObligationAgreements (retainer, project milestones, etc.)
- Each ExpenseBucket to have multiple ObligationAgreements
- Full traceability from obligations back to source entities

Revision ID: l8m9n0o1p2q3
Revises: k7l8m9n0o1p2
Create Date: 2026-01-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'l8m9n0o1p2q3'
down_revision: Union[str, None] = 'k7l8m9n0o1p2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add client_id FK to obligation_agreements
    # This enables One-to-Many: Client -> ObligationAgreement
    op.add_column(
        'obligation_agreements',
        sa.Column('client_id', sa.String(), nullable=True)
    )
    op.create_foreign_key(
        'fk_obligation_agreements_client_id',
        'obligation_agreements',
        'clients',
        ['client_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index(
        'ix_obligation_agreements_client_id',
        'obligation_agreements',
        ['client_id']
    )

    # Add expense_bucket_id FK to obligation_agreements
    # This enables One-to-Many: ExpenseBucket -> ObligationAgreement
    op.add_column(
        'obligation_agreements',
        sa.Column('expense_bucket_id', sa.String(), nullable=True)
    )
    op.create_foreign_key(
        'fk_obligation_agreements_expense_bucket_id',
        'obligation_agreements',
        'expense_buckets',
        ['expense_bucket_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index(
        'ix_obligation_agreements_expense_bucket_id',
        'obligation_agreements',
        ['expense_bucket_id']
    )


def downgrade() -> None:
    # Remove expense_bucket_id FK and column
    op.drop_index('ix_obligation_agreements_expense_bucket_id', table_name='obligation_agreements')
    op.drop_constraint('fk_obligation_agreements_expense_bucket_id', 'obligation_agreements', type_='foreignkey')
    op.drop_column('obligation_agreements', 'expense_bucket_id')

    # Remove client_id FK and column
    op.drop_index('ix_obligation_agreements_client_id', table_name='obligation_agreements')
    op.drop_constraint('fk_obligation_agreements_client_id', 'obligation_agreements', type_='foreignkey')
    op.drop_column('obligation_agreements', 'client_id')
