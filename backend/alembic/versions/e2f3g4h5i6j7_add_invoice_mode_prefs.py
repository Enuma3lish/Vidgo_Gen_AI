"""add user invoice-mode preference (統編/載具/捐贈 auto-issue setting)

Adds three columns to users so the buyer can decide, in 發票設定, how every
future invoice is issued automatically after payment:
  - default_invoice_mode        'carrier' | 'donation' | 'b2b' (NULL = legacy inference)
  - default_buyer_tax_id        統一編號 (8 digits, B2B mode)
  - default_buyer_company_name  公司抬頭 (B2B mode)

Statements use IF NOT EXISTS so the migration is also safe to pre-apply
manually (the prod rollout on 2026-06-12 applied the SQL via a one-off
Cloud Run job before this revision ran at startup).

NOTE: down_revision must be the CURRENT chain head (the production
entrypoint runs `alembic upgrade head` on boot and refuses to start when
multiple heads exist). Chaining off a mid-chain revision broke revision
vidgo-backend-00332 — keep this on the linear chain.

Revision ID: e2f3g4h5i6j7
Revises: j4d5e6f7g8h9
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e2f3g4h5i6j7'
down_revision: Union[str, None] = 'j4d5e6f7g8h9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS default_invoice_mode VARCHAR(10)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS default_buyer_tax_id VARCHAR(8)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS default_buyer_company_name VARCHAR(100)")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS default_buyer_company_name")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS default_buyer_tax_id")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS default_invoice_mode")
