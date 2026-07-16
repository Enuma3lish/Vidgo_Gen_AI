"""International (USD) credit-pack price bump — light/standard/heavy (2026-07-16).

Revision ID: q9r0s1t2u3v4
Revises: p8q9r0s1t2u3
Create Date: 2026-07-16

Operator retier of the INTERNATIONAL (PayPal/USD) top-up credit packs only:

    light_pack     (250 cr)  US$9.99  ->  US$10.79
    standard_pack  (416 cr)  US$16.99 ->  US$18.35
    heavy_pack     (833 cr)  US$32.99 ->  US$35.62

Why a migration and not the seed constant: ``seed_new_pricing_tiers.py`` only
inserts on a fresh DB — production rows are already seeded so bumping
NEW_CREDIT_PACKAGE_DATA alone leaves live rows at the old price and PayPal
checkout keeps charging the stale amount (credits/purchase reads
``package.price_usd`` off the DB row). Mirrors p8q9r0s1t2u3 which did the
same for subscription plans.

Touches ONLY the USD side: ``price_usd``. Leaves ``price_twd`` (299/499/999)
and ``credits`` (250/416/833) untouched — the Taiwan NT$/ECPay packs and
credit amounts are unchanged.

Idempotent: sets absolute values keyed by pack name, safe to re-run.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "q9r0s1t2u3v4"
down_revision: Union[str, None] = "p8q9r0s1t2u3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# name -> price_usd. USD side only.
_NEW_INTL = {
    "light_pack":    "10.79",
    "standard_pack": "18.35",
    "heavy_pack":    "35.62",
}
# Prior values, for downgrade().
_OLD_INTL = {
    "light_pack":    "9.99",
    "standard_pack": "16.99",
    "heavy_pack":    "32.99",
}


def _apply(values: dict) -> None:
    bind = op.get_bind()
    stmt = sa.text(
        "UPDATE credit_packages SET price_usd = :price_usd WHERE name = :name"
    )
    for name, price_usd in values.items():
        bind.execute(stmt, {"name": name, "price_usd": price_usd})


def upgrade() -> None:
    _apply(_NEW_INTL)


def downgrade() -> None:
    _apply(_OLD_INTL)
