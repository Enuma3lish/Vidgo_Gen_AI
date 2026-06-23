"""Add billing_cycle column to subscriptions

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-23

The Subscription model and four read sites (webhook activation in
subscription_service.handle_payment_success, the recurring-credit worker, and
credit_service) all read `subscription.billing_cycle`, but the column was never
created — only `plans.billing_cycle` existed. Reading an undeclared attribute on
the SQLAlchemy model raised AttributeError, which silently failed every
webhook-driven PayPal subscription activation (customer charged, no plan, no
credits, non-retryable 200). This adds the missing per-subscription column.

Idempotent ADD COLUMN IF NOT EXISTS + best-effort backfill of 'yearly' from the
creating order's payment_data, so it is safe to replay (prod alembic history has
multiple heads and is applied manually).
"""
from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {
        row[0] for row in bind.exec_driver_sql(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'subscriptions'"
        ).fetchall()
    }
    if "billing_cycle" not in existing:
        op.add_column(
            "subscriptions",
            sa.Column("billing_cycle", sa.String(), nullable=False, server_default="monthly"),
        )

    # Best-effort backfill: mark existing subscriptions 'yearly' when their
    # creating order recorded a yearly cycle. New rows default to 'monthly'
    # (server_default), which is correct for the monthly majority. Guarded so a
    # non-JSON payment_data column or any other surprise can't break the upgrade.
    try:
        bind.exec_driver_sql(
            """
            UPDATE subscriptions s
            SET billing_cycle = 'yearly'
            FROM orders o
            WHERE o.subscription_id = s.id
              AND (o.payment_data ->> 'billing_cycle') = 'yearly'
              AND s.billing_cycle <> 'yearly'
            """
        )
    except Exception:
        # Backfill is opportunistic; the server_default already makes the column
        # safe to read. Leave existing rows as 'monthly' if the JSON probe fails.
        pass


def downgrade() -> None:
    bind = op.get_bind()
    existing = {
        row[0] for row in bind.exec_driver_sql(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'subscriptions'"
        ).fetchall()
    }
    if "billing_cycle" in existing:
        op.drop_column("subscriptions", "billing_cycle")
