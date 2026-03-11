"""add taiwan e-invoice fields and invoice_items table

Revision ID: s1t2u3v4w5x6
Revises: r1s2t3u4v5w6
Create Date: 2026-03-11 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 's1t2u3v4w5x6'
down_revision: Union[str, None] = 'r1s2t3u4v5w6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === Enhance invoices table with Taiwan e-invoice fields ===
    op.add_column('invoices', sa.Column('invoice_type', sa.String(10), nullable=True, server_default='b2c'))
    op.add_column('invoices', sa.Column('tax_type', sa.String(20), nullable=True, server_default='taxable'))
    op.add_column('invoices', sa.Column('tax_rate', sa.DECIMAL(5, 4), nullable=True, server_default='0.05'))
    op.add_column('invoices', sa.Column('tax_amount', sa.DECIMAL(10, 2), nullable=True))
    op.add_column('invoices', sa.Column('sales_amount', sa.DECIMAL(10, 2), nullable=True))

    # Buyer info (B2B)
    op.add_column('invoices', sa.Column('buyer_company_name', sa.String(100), nullable=True))
    op.add_column('invoices', sa.Column('buyer_tax_id', sa.String(8), nullable=True))

    # Buyer info (B2C)
    op.add_column('invoices', sa.Column('buyer_email', sa.String(255), nullable=True))

    # Carrier info (B2C)
    op.add_column('invoices', sa.Column('carrier_type', sa.String(20), nullable=True))
    op.add_column('invoices', sa.Column('carrier_number', sa.String(64), nullable=True))

    # Donation (B2C)
    op.add_column('invoices', sa.Column('is_donation', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('invoices', sa.Column('love_code', sa.String(7), nullable=True))

    # ECPay tracking
    op.add_column('invoices', sa.Column('ecpay_invoice_no', sa.String(20), nullable=True))
    op.add_column('invoices', sa.Column('ecpay_relate_number', sa.String(30), nullable=True))
    op.add_column('invoices', sa.Column('ecpay_response_data', postgresql.JSONB(), nullable=True))

    # Invoice period
    op.add_column('invoices', sa.Column('invoice_period', sa.String(6), nullable=True))

    # Void tracking
    op.add_column('invoices', sa.Column('status', sa.String(20), nullable=True, server_default='issued'))
    op.add_column('invoices', sa.Column('voided_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('invoices', sa.Column('void_reason', sa.String(255), nullable=True))
    op.add_column('invoices', sa.Column('void_response_data', postgresql.JSONB(), nullable=True))
    op.add_column('invoices', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))

    # Create unique index on ecpay_relate_number
    op.create_index('ix_invoices_ecpay_relate_number', 'invoices', ['ecpay_relate_number'], unique=True)

    # Make order_id nullable (for pending invoices before order assignment)
    op.alter_column('invoices', 'order_id', nullable=True)

    # === Create invoice_items table ===
    op.create_table(
        'invoice_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False),
        sa.Column('item_name', sa.String(255), nullable=False),
        sa.Column('item_count', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('item_unit', sa.String(10), nullable=True, server_default='式'),
        sa.Column('item_price', sa.DECIMAL(10, 2), nullable=False),
        sa.Column('item_amount', sa.DECIMAL(10, 2), nullable=False),
        sa.Column('item_tax_type', sa.String(20), nullable=True, server_default='taxable'),
    )
    op.create_index('ix_invoice_items_invoice_id', 'invoice_items', ['invoice_id'])

    # === Add e-invoice preferences to users table ===
    op.add_column('users', sa.Column('default_carrier_type', sa.String(20), nullable=True))
    op.add_column('users', sa.Column('default_carrier_number', sa.String(64), nullable=True))
    op.add_column('users', sa.Column('default_love_code', sa.String(7), nullable=True))


def downgrade() -> None:
    # Drop user e-invoice preferences
    op.drop_column('users', 'default_love_code')
    op.drop_column('users', 'default_carrier_number')
    op.drop_column('users', 'default_carrier_type')

    # Drop invoice_items table
    op.drop_index('ix_invoice_items_invoice_id', table_name='invoice_items')
    op.drop_table('invoice_items')

    # Drop invoice indexes
    op.drop_index('ix_invoices_ecpay_relate_number', table_name='invoices')

    # Drop e-invoice columns from invoices
    for col in [
        'updated_at', 'void_response_data', 'void_reason', 'voided_at', 'status',
        'invoice_period', 'ecpay_response_data', 'ecpay_relate_number', 'ecpay_invoice_no',
        'love_code', 'is_donation', 'carrier_number', 'carrier_type',
        'buyer_email', 'buyer_tax_id', 'buyer_company_name',
        'sales_amount', 'tax_amount', 'tax_rate', 'tax_type', 'invoice_type',
    ]:
        op.drop_column('invoices', col)
