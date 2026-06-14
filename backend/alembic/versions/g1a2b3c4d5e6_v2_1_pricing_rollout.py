"""Pricing v2.1 rollout — subscription plans, packs, per-feature costs.

Revision ID: g1a2b3c4d5e6
Revises: f1a2b3c4d5e6
Create Date: 2026-05-22

Owner-approved spec 修正單 v2.1. Recalibrates the SaaS price points after the
v2.0 launch revealed the credit yields were ~10× too generous, turning every
paid generation into a margin loss.

Changes in one migration so the live site flips atomically:

1. **Plans repriced + recredited** (basic→Standard, pro→Pro, premium→Advanced,
   enterprise→Enterprise "Contact Us"). Display names switch to the v2.1
   vocabulary; internal slugs (basic/pro/premium/enterprise) are unchanged
   so plan_gates.py, payment provider IDs, and FK references keep working.

   |  slug      | display       | TWD    | USD       | credits | resolution |
   |  ---       | ---           | ---    | ---       | ---     | ---        |
   |  basic     | 標準版 Standard | 399   | 19.99     | 450     | 1080p HD   |
   |  pro       | 專業版 Pro     | 999   | 49.99     | 1,200   | 4K         |
   |  premium   | 進階版 Advanced | 1,699 | 89.99     | 2,200   | 4K         |
   |  enterprise| 企業版          | 0     | 0         | 0       | 4K (custom)|

   Enterprise becomes "Contact Us" — price_twd/price_usd zeroed so the front
   end can render the contact CTA, monthly_credits = 0 (custom on request).

2. **Credit packs sized to NT$1.20–1.00/credit** (graduated discount per spec):

   |  name           | credits | TWD  | USD  | NT$/cr |
   |  ---            | ---     | ---  | ---  | ---    |
   |  light_pack     | 250     | 299  | 9.99 | 1.196  |
   |  standard_pack  | 450     | 499  | 16.99| 1.109  |
   |  heavy_pack     | 1,000   | 999  | 32.99| 0.999  |

   This OVERRIDES the in-flight f1a2b3c4d5e6 migration's 416/833 values to
   the v2.1-spec rounded 450/1000.

3. **Per-feature service_pricing.credit_cost recalibrated** to match v2.1's
   "what 100 credits does for you" marketing math. Where no row exists for
   a service_type, the migration inserts a new one.

   - 標準 AI 圖片 (text_to_image_default):  20 →  1
   - 高品質 AI 圖片 (image_generation_premium): 50 →  5
   - 標準 AI 影片 5-10s (short_video / video_generation_standard): 25 → 20
   - 專業長影片 Kling 10s (video_generation_professional): 35/60 → 60
   - 畫質修復 (image_upscale / video_upscale): 15
   - 新: veo3_video → 200
   - 新: seedance_wan_video → 40   (Seedance / Wan I2V via short-video)

Downgrade restores the pre-v2.1 values inserted by f1a2b3c4d5e6 / the seed
script.
"""

import json
import uuid
from decimal import Decimal
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g1a2b3c4d5e6"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── New plan values. Display names are bilingual.
NEW_PLAN_VALUES = [
    {
        "name":            "basic",
        "display_name":    "標準版 Standard",
        "price_twd":       Decimal("399"),
        "price_usd":       Decimal("19.99"),
        "price_monthly":   399.0,
        "price_yearly":    3990.0,
        "monthly_credits": 450,
        "max_resolution": "1080p",
    },
    {
        "name":            "pro",
        "display_name":    "專業版 Pro",
        "price_twd":       Decimal("999"),
        "price_usd":       Decimal("49.99"),
        "price_monthly":   999.0,
        "price_yearly":    9990.0,
        "monthly_credits": 1200,
        "max_resolution": "4k",
    },
    {
        "name":            "premium",
        "display_name":    "進階版 Advanced",
        "price_twd":       Decimal("1699"),
        "price_usd":       Decimal("89.99"),
        "price_monthly":   1699.0,
        "price_yearly":    16990.0,
        "monthly_credits": 2200,
        "max_resolution": "4k",
    },
    {
        "name":            "enterprise",
        "display_name":    "企業版 Enterprise",
        # Zero pricing means the frontend renders the "Contact Us" CTA
        # instead of a buy button. Credits/features are negotiated case-
        # by-case and provisioned via the admin panel.
        "price_twd":       Decimal("0"),
        "price_usd":       Decimal("0"),
        "price_monthly":   0.0,
        "price_yearly":    0.0,
        "monthly_credits": 0,
        "max_resolution": "4k",
    },
]

# Pre-v2.1 plan values for downgrade — mirrors the post-f1a2b3c4d5e6 state.
OLD_PLAN_VALUES = [
    {"name": "basic",      "display_name": "基礎進階版", "price_twd": Decimal("699"),   "price_usd": Decimal("22"),  "price_monthly": 699.0,   "price_yearly": 6990.0,   "monthly_credits": 7000,   "max_resolution": "720p"},
    {"name": "pro",        "display_name": "專業版",     "price_twd": Decimal("999"),   "price_usd": Decimal("32"),  "price_monthly": 999.0,   "price_yearly": 9990.0,   "monthly_credits": 10000,  "max_resolution": "1080p"},
    {"name": "premium",    "display_name": "尊榮版",     "price_twd": Decimal("1699"),  "price_usd": Decimal("55"),  "price_monthly": 1699.0,  "price_yearly": 16990.0,  "monthly_credits": 18000,  "max_resolution": "4k"},
    {"name": "enterprise", "display_name": "企業旗艦版", "price_twd": Decimal("15000"), "price_usd": Decimal("485"), "price_monthly": 15000.0, "price_yearly": 150000.0, "monthly_credits": 160000, "max_resolution": "4k"},
]

# New pack values — rounded to spec, override f1a2b3c4d5e6's 416/833.
NEW_PACK_VALUES = [
    {"name": "light_pack",    "credits": 250,  "price_twd": Decimal("299"), "price_usd": Decimal("9.99")},
    {"name": "standard_pack", "credits": 450,  "price_twd": Decimal("499"), "price_usd": Decimal("16.99")},
    {"name": "heavy_pack",    "credits": 1000, "price_twd": Decimal("999"), "price_usd": Decimal("32.99")},
]

# Per-feature credit costs (v2.1 spec).
NEW_SERVICE_PRICING_COSTS = {
    "text_to_image_default":        1,
    "image_generation_default":     1,    # legacy alias used in some endpoints
    "image_generation_premium":     5,
    "short_video":                 20,
    "video_generation_standard":   20,
    "video_generation_professional": 60,
    "image_upscale":               15,
    "video_upscale":               15,
}

# Brand-new service_type rows. INSERT … ON CONFLICT keeps re-runs safe.
NEW_SERVICE_PRICING_INSERTS = [
    {
        "service_type": "veo3_video",
        "display_name": "Veo 3.1 影片 (5s)",
        "credit_cost": 200,
        "api_cost_usd": Decimal("0.500"),
        "model_type": "veo",
        "tool_category": "premium",
        "tool_type": "text_to_video",
        "resolution": "1080p",
        "max_duration": 5,
        "subscribers_only": True,
        "min_plan": "premium",
        "allowed_models": ["veo"],
        "description": "Veo 3.1 旗艦影片 - 文生影片 5 秒",
    },
    {
        "service_type": "seedance_wan_video",
        "display_name": "Seedance / Wan 影片",
        "credit_cost": 40,
        "api_cost_usd": Decimal("0.100"),
        "model_type": "default",
        "tool_category": "dynamic",
        "tool_type": "image_to_video",
        "resolution": "1080p",
        "max_duration": 10,
        "subscribers_only": True,
        "min_plan": "pro",
        "allowed_models": ["seedance", "wan"],
        "description": "Seedance / Wan 動態影片 (中價位)",
    },
]


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. Update plans (display_name + price + credits + max_resolution).
    for p in NEW_PLAN_VALUES:
        bind.execute(
            sa.text("""
                UPDATE plans
                   SET display_name    = :display_name,
                       price_twd       = :price_twd,
                       price_usd       = :price_usd,
                       price_monthly   = :price_monthly,
                       price_yearly    = :price_yearly,
                       monthly_credits = :monthly_credits,
                       max_resolution  = :max_resolution
                 WHERE name = :name
            """),
            p,
        )

    # ── 2. Override credit_packages to v2.1 graduated tiers.
    for pack in NEW_PACK_VALUES:
        bind.execute(
            sa.text("""
                UPDATE credit_packages
                   SET credits   = :credits,
                       price_twd = :price_twd,
                       price_usd = :price_usd,
                       price     = :price_legacy
                 WHERE name = :name
            """),
            {**pack, "price_legacy": float(pack["price_twd"])},
        )

    # ── 3. Update per-feature credit costs (only rows that already exist).
    for service_type, cost in NEW_SERVICE_PRICING_COSTS.items():
        bind.execute(
            sa.text("""
                UPDATE service_pricing
                   SET credit_cost = :cost
                 WHERE service_type = :service_type
            """),
            {"service_type": service_type, "cost": cost},
        )

    # ── 4. INSERT new service_pricing rows (Veo 3.1 + Seedance/Wan).
    # service_pricing.id is `default=uuid.uuid4` at the ORM layer (no SQL
    # default), so a raw INSERT must supply the UUID explicitly — otherwise
    # we hit NotNullViolationError on the id column and the whole migration
    # rolls back (seen in production 2026-05-22).
    for row in NEW_SERVICE_PRICING_INSERTS:
        bind.execute(
            sa.text("""
                INSERT INTO service_pricing (
                    id, service_type, display_name, credit_cost, api_cost_usd,
                    model_type, tool_category, tool_type, resolution,
                    max_duration, subscribers_only, min_plan, allowed_models,
                    description, is_active, created_at, updated_at
                )
                VALUES (
                    CAST(:id AS UUID),
                    :service_type, :display_name, :credit_cost, :api_cost_usd,
                    :model_type, :tool_category, :tool_type, :resolution,
                    :max_duration, :subscribers_only, :min_plan,
                    CAST(:allowed_models AS JSON),
                    :description, TRUE, NOW(), NOW()
                )
                ON CONFLICT (service_type) DO UPDATE SET
                    credit_cost      = EXCLUDED.credit_cost,
                    api_cost_usd     = EXCLUDED.api_cost_usd,
                    display_name     = EXCLUDED.display_name,
                    description      = EXCLUDED.description,
                    min_plan         = EXCLUDED.min_plan,
                    allowed_models   = EXCLUDED.allowed_models,
                    updated_at       = NOW()
            """),
            {
                **row,
                "id": str(uuid.uuid4()),
                "allowed_models": json.dumps(row["allowed_models"]),
            },
        )


def downgrade() -> None:
    bind = op.get_bind()

    # Restore plan rows.
    for p in OLD_PLAN_VALUES:
        bind.execute(
            sa.text("""
                UPDATE plans
                   SET display_name    = :display_name,
                       price_twd       = :price_twd,
                       price_usd       = :price_usd,
                       price_monthly   = :price_monthly,
                       price_yearly    = :price_yearly,
                       monthly_credits = :monthly_credits,
                       max_resolution  = :max_resolution
                 WHERE name = :name
            """),
            p,
        )

    # Restore pack values to the post-f1a2b3c4d5e6 baseline (250/416/833).
    OLD_PACKS = [
        {"name": "light_pack",    "credits": 250, "price_twd": Decimal("299"), "price_usd": Decimal("10")},
        {"name": "standard_pack", "credits": 416, "price_twd": Decimal("499"), "price_usd": Decimal("16")},
        {"name": "heavy_pack",    "credits": 833, "price_twd": Decimal("999"), "price_usd": Decimal("32")},
    ]
    for pack in OLD_PACKS:
        bind.execute(
            sa.text("""
                UPDATE credit_packages
                   SET credits   = :credits,
                       price_twd = :price_twd,
                       price_usd = :price_usd,
                       price     = :price_legacy
                 WHERE name = :name
            """),
            {**pack, "price_legacy": float(pack["price_twd"])},
        )

    # Restore prior service_pricing costs.
    OLD_COSTS = {
        "text_to_image_default":          20,
        "image_generation_default":       20,
        "image_generation_premium":       50,
        "short_video":                    25,
        "video_generation_standard":     100,
        "video_generation_professional": 300,
        "image_upscale":                  50,
        "video_upscale":                  50,
    }
    for service_type, cost in OLD_COSTS.items():
        bind.execute(
            sa.text("""
                UPDATE service_pricing
                   SET credit_cost = :cost
                 WHERE service_type = :service_type
            """),
            {"service_type": service_type, "cost": cost},
        )

    # Remove the new rows added in upgrade.
    for row in NEW_SERVICE_PRICING_INSERTS:
        bind.execute(
            sa.text("DELETE FROM service_pricing WHERE service_type = :st"),
            {"st": row["service_type"]},
        )
