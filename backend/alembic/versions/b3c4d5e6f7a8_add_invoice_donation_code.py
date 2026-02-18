"""Add donation_code column to invoices table

Revision ID: b3c4d5e6f7a8
Revises: 99d728708134
Create Date: 2026-02-18

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b3c4d5e6f7a8'
down_revision = '99d728708134'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('invoices', sa.Column('donation_code', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('invoices', 'donation_code')
