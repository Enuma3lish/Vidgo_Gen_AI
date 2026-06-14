"""Lock legacy packs, sync plan.allowed_models, reprice the 3 official packs.

Revision ID: f1a2b3c4d5e6
Revises: e7f8a9b0c1d2
Create Date: 2026-05-20

Three defensive backend changes, all motivated by margin-bleed risk:

1. **Legacy credit-pack backdoor.** /credits/purchase already whitelists by
   ``name in ('light_pack','standard_pack','heavy_pack')``, but old rows
   (small/medium/large/pack_v1) may sit with ``is_active=true`` from
   pre-May-2026 seeds. Belt-and-suspenders: explicitly deactivate them.

2. **Plan.allowed_models vocabulary.** Pre-today the seed used abstract
   labels (``default``, ``wan_pro``, ``gemini_pro``) that didn't match the
   model IDs the frontend sends. ``plan_gates.require_model_access`` does
   substring matching against a curated floor map, so the column isn't
   strictly required by the gate — but we sync it so admin reads reflect
   what each tier can actually do.

3. **Pack repricing to NT$1.20/credit (owner directive 2026-05-20).** The
   previous pack tiers (3000 / 5500 / 12000 credits) sold below cost. New
   values (250 / 416 / 833 credits at NT$299 / NT$499 / NT$999) lift the
   per-credit price 12x. Per-generation deduction weights are unchanged,
   so the change is purely a packaging adjustment — existing users keep
   credits they already bought, but every new top-up lands at the new rate.

All operations are idempotent and have full downgrades.
"""

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Matches OFFICIAL_CREDIT_PACKAGE_NAMES in backend/app/services/credit_service.py
OFFICIAL_PACK_NAMES = ("light_pack", "standard_pack", "heavy_pack")

# Plan name → models the gate considers accessible at that tier.
# Mirrors PLAN_FLOOR_FOR_MODEL in backend/app/services/plan_gates.py
# (conservative variant approved 2026-05-20).
PLAN_ALLOWED_MODELS = {
    "basic":      ["flux", "seedance", "z-image"],
    "pro":        ["flux", "seedance", "z-image", "qwen", "kling", "hailuo", "hunyuan", "wan"],
    "premium":    ["flux", "seedance", "z-image", "qwen", "kling", "hailuo", "hunyuan", "wan", "kling_flagship", "kling_omni", "veo"],
    "enterprise": ["flux", "seedance", "z-image", "qwen", "kling", "hailuo", "hunyuan", "wan", "kling_flagship", "kling_omni", "veo", "sora"],
}

# New per-pack pricing (NT$1.20/credit). Migration sets credits + clears
# bonus_credits so the columns match the seed exactly. price_twd / price_usd
# are unchanged — only the credit yield drops.
NEW_PACK_VALUES = [
    {"name": "light_pack",    "credits": 250, "bonus_credits": 0},
    {"name": "standard_pack", "credits": 416, "bonus_credits": 0},
    {"name": "heavy_pack",    "credits": 833, "bonus_credits": 0},
]

# Pre-2026-05-20 pack values, for downgrade. Restored as-was, so a rollback
# returns the DB to the prior state operators were familiar with.
OLD_PACK_VALUES = [
    {"name": "light_pack",    "credits": 3000,  "bonus_credits": 0},
    {"name": "standard_pack", "credits": 5500,  "bonus_credits": 500},
    {"name": "heavy_pack",    "credits": 12000, "bonus_credits": 2000},
]


def upgrade() -> None:
    bind = op.get_bind()

    # ── Risk 1: deactivate any credit_packages row that isn't on the official list.
    # Legacy rows keep their data but become invisible to the purchase endpoint
    # (which filters on is_active=True).
    bind.execute(
        sa.text(
            """
            UPDATE credit_packages
               SET is_active = FALSE
             WHERE name NOT IN :official_names
               AND is_active = TRUE
            """
        ).bindparams(sa.bindparam("official_names", expanding=True)),
        {"official_names": list(OFFICIAL_PACK_NAMES)},
    )

    # ── Risk 2: sync plans.allowed_models to the new vocabulary, by plan name.
    # CAST the JSON literal so PostgreSQL stores it as JSON not text.
    for plan_name, models in PLAN_ALLOWED_MODELS.items():
        bind.execute(
            sa.text(
                """
                UPDATE plans
                   SET allowed_models = CAST(:models AS JSON)
                 WHERE name = :plan_name
                """
            ),
            {"plan_name": plan_name, "models": json.dumps(models)},
        )

    # ── Risk 3: reprice the three official packs to NT$1.20/credit.
    # We touch only credits + bonus_credits — price_twd / price_usd / display
    # copy are unchanged (sales messaging didn't shift, only the bundle size).
    for pack in NEW_PACK_VALUES:
        bind.execute(
            sa.text(
                """
                UPDATE credit_packages
                   SET credits       = :credits,
                       bonus_credits = :bonus_credits
                 WHERE name = :pack_name
                """
            ),
            {
                "pack_name":     pack["name"],
                "credits":       pack["credits"],
                "bonus_credits": pack["bonus_credits"],
            },
        )


def downgrade() -> None:
    bind = op.get_bind()

    # Restore legacy packs to is_active=True. This is the safest reversible
    # outcome — operators can always re-disable them by re-running upgrade.
    bind.execute(
        sa.text(
            """
            UPDATE credit_packages
               SET is_active = TRUE
             WHERE name NOT IN :official_names
            """
        ).bindparams(sa.bindparam("official_names", expanding=True)),
        {"official_names": list(OFFICIAL_PACK_NAMES)},
    )

    # Restore the legacy abstract vocabulary on plans.allowed_models so the
    # downgrade matches the pre-migration seed (see seed_new_pricing_tiers.py
    # circa 2026-05-19).
    LEGACY = {
        "basic":      ["default"],
        "pro":        ["default", "wan_pro", "gemini_pro"],
        "premium":    ["default", "wan_pro", "gemini_pro"],
        "enterprise": ["default", "wan_pro", "gemini_pro", "sora"],
    }
    for plan_name, models in LEGACY.items():
        bind.execute(
            sa.text(
                """
                UPDATE plans
                   SET allowed_models = CAST(:models AS JSON)
                 WHERE name = :plan_name
                """
            ),
            {"plan_name": plan_name, "models": json.dumps(models)},
        )

    # Restore pack credit yields to pre-2026-05-20 values.
    for pack in OLD_PACK_VALUES:
        bind.execute(
            sa.text(
                """
                UPDATE credit_packages
                   SET credits       = :credits,
                       bonus_credits = :bonus_credits
                 WHERE name = :pack_name
                """
            ),
            {
                "pack_name":     pack["name"],
                "credits":       pack["credits"],
                "bonus_credits": pack["bonus_credits"],
            },
        )
