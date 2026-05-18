"""Add payment_settings table for admin-editable PayPal config

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-05-17

Adds a single-row table that lets admins flip PayPal sandbox ↔ production
and rotate credentials / plan IDs from /admin/settings/payment without
redeploying. PaymentSettingsService reads DB first; missing columns fall
back to the values mounted on Cloud Run from Secret Manager.

Secrets (`paypal_client_secret_encrypted`) are encrypted at rest via
Fernet keyed off settings.SECRET_KEY (same key JWT signing uses) so a DB
dump alone never leaks the live secret.
"""
from alembic import op
import sqlalchemy as sa


revision = 'e7f8a9b0c1d2'
down_revision = 'd6e7f8a9b0c1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'payment_settings',
        sa.Column('id', sa.Integer(), primary_key=True, default=1),
        sa.Column('paypal_env', sa.String(length=20), nullable=True),
        sa.Column('paypal_client_id', sa.String(length=255), nullable=True),
        sa.Column('paypal_client_secret_encrypted', sa.Text(), nullable=True),
        sa.Column('paypal_webhook_id', sa.String(length=120), nullable=True),
        sa.Column('paypal_plan_ids', sa.Text(), nullable=True),
        sa.Column('updated_by', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Seed the singleton row so subsequent UPDATEs always have a target;
    # PaymentSettingsService does UPSERT-style write but the GET path
    # is simpler if the row is guaranteed to exist.
    op.execute("INSERT INTO payment_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING")


def downgrade() -> None:
    op.drop_table('payment_settings')
