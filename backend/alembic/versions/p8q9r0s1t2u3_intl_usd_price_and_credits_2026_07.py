"""International (USD) price + credit re-tier — Basic/Pro/Premium (2026-07-16).

Revision ID: p8q9r0s1t2u3
Revises: k7m8n9o0p1q2
Create Date: 2026-07-16

Operator retier of the INTERNATIONAL (PayPal/USD) plans only:

    Basic    US$19.99 / 400 credits  ->  US$22.99 /  330 credits
    Pro      US$49.99 / 1000 credits ->  US$59.99 /  850 credits
    Premium  US$89.99 / 1800 credits ->  US$99.99 / 1400 credits

Why a migration and not the seed constant: ``ensure_vidgo_plans`` in
app/api/v1/subscriptions.py is INSERT-ONLY — it never overwrites existing plan
rows (admin edits in /admin/plans are the source of truth once a row exists).
So bumping DEFAULT_VIDGO_PLANS alone leaves every already-seeded production row
at the old price/credits, and /pricing keeps showing the stale numbers. This
migration writes the new values onto the live rows so the frontend matches.

Touches ONLY the USD side: ``price_usd`` and ``monthly_credits`` (the allowance
USD/PayPal subscribers receive). It deliberately leaves ``monthly_credits_twd``
(350 / 900 / 1600), ``price_twd`` and ``price_monthly`` untouched — the Taiwan
NT$/ECPay plans are unchanged.

Idempotent: sets absolute values keyed by plan name, safe to re-run.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p8q9r0s1t2u3"
# Chained off the current alembic head (k7m8n9o0p1q2 split_sora2_std_pro_pricing,
# 2026-07-12). Chaining anywhere else would leave a second dangling head and
# docker_entrypoint.sh's `alembic upgrade head` would refuse to start.
down_revision: Union[str, None] = "k7m8n9o0p1q2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# name -> (price_usd, monthly_credits). USD side only.
_NEW_INTL = {
    "basic":   ("22.99", 330),
    "pro":     ("59.99", 850),
    "premium": ("99.99", 1400),
}
# Prior values, for downgrade().
_OLD_INTL = {
    "basic":   ("19.99", 400),
    "pro":     ("49.99", 1000),
    "premium": ("89.99", 1800),
}


def _apply(values: dict) -> None:
    bind = op.get_bind()
    stmt = sa.text(
        "UPDATE plans SET price_usd = :price_usd, monthly_credits = :credits "
        "WHERE name = :name"
    )
    for name, (price_usd, credits) in values.items():
        bind.execute(
            stmt,
            {"name": name, "price_usd": price_usd, "credits": credits},
        )


def upgrade() -> None:
    _apply(_NEW_INTL)


def downgrade() -> None:
    _apply(_OLD_INTL)
