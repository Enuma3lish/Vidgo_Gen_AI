"""widen buyer_tax_id columns for international (PayPal) VAT/EIN

PayPal checkout is shown only to overseas buyers, whose company tax/VAT id is
NOT a Taiwan 8-digit 統編 (e.g. GB/DE VAT, US EIN). Widen the two persisted
tax-id columns from VARCHAR(8) to VARCHAR(20) so an international id can be
stored and later printed on the PayPal Invoicing v2 invoice:
  - users.default_buyer_tax_id    (saved B2B preference, drives auto_issue)
  - invoices.buyer_tax_id         (issued invoice record)

Widening a varchar length in PostgreSQL is a metadata-only change (no table
rewrite, no lock escalation). The TW 統編 (8 digits) still fits unchanged, so
this is backward-compatible for the ECPay/Giveme path.

NOTE: down_revision must be the CURRENT chain head — the prod entrypoint runs
`alembic upgrade head` on boot and refuses to start when multiple heads exist.

Revision ID: k5l6m7n8o9p0
Revises: c1ta2sk3id45
Create Date: 2026-06-27 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'k5l6m7n8o9p0'
down_revision: Union[str, None] = 'c1ta2sk3id45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN default_buyer_tax_id TYPE VARCHAR(20)")
    op.execute("ALTER TABLE invoices ALTER COLUMN buyer_tax_id TYPE VARCHAR(20)")


def downgrade() -> None:
    # Narrowing requires an explicit USING cast; truncate to 8 so any stored
    # international id doesn't fail the narrower type (TW 統編 already fits).
    op.execute("ALTER TABLE users ALTER COLUMN default_buyer_tax_id TYPE VARCHAR(8) USING LEFT(default_buyer_tax_id, 8)")
    op.execute("ALTER TABLE invoices ALTER COLUMN buyer_tax_id TYPE VARCHAR(8) USING LEFT(buyer_tax_id, 8)")
