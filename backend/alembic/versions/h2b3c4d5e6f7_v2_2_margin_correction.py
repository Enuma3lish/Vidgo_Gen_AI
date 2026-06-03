"""Pricing v2.2 margin correction — fix sub-cost defaults, close pack arbitrage.

Revision ID: h2b3c4d5e6f7
Revises: p5q6r7s8t9u0
Create Date: 2026-06-03

Follow-up to v2.1 (g1a2b3c4d5e6) after a margin audit (docs/service-cost.md)
showed three structural leaks:

1. Several `service_type` strings used in `app/api/v1/tools.py` did not match
   the seeded `service_pricing.service_type` keys — so the v2.1 "deduction
   firewall" was silently dead for `background_removal`, `product_scene`,
   `upscale`. The code was renamed to match; this migration ensures the rows
   actually exist and carry the v2.2-spec credit_cost.

2. `tier_config.CREDIT_COSTS` (the fallback when no DB row matches) still
   carried v2.0 numbers. Avatar / try-on / lip-sync at 10–30 credits cost
   the platform more upstream ($0.50–$3.00) than the cheapest pack rate
   ($0.033/credit) yields in revenue. The fallback table was raised in
   code; this migration mirrors the same costs into service_pricing for
   the DB-driven path.

3. heavy_pack at 1,000 cr / NT$999 (NT$0.999/cr ≈ $0.033/cr) undercut even
   the cheapest subscription tier (basic = NT$0.887/cr but USD $0.0444/cr).
   Heavy users would always buy packs, capping blended yield. Rerate to
   850 cr / NT$999 (NT$1.175/cr, $0.0388/cr) so the cheapest subscription
   is once again the cheapest credit source.

Upgrade is idempotent. Downgrade restores v2.1 values.
"""

import json
import uuid
from decimal import Decimal
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h2b3c4d5e6f7"
down_revision: Union[str, None] = "p5q6r7s8t9u0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ─── v2.2 service_pricing values ─────────────────────────────────────────
# credit_cost matches tier_config.CREDIT_COSTS default values exactly.
# api_cost_usd is a realistic 2026-Q2 PiAPI / A2E / Vertex estimate; ops
# should reconcile against monthly vendor invoices and rerun P3 seeding.
NEW_SERVICE_PRICING_VALUES = {
    # --- existing rows re-priced ---
    "background_removal":        {"cost": 3,   "usd": Decimal("0.020")},
    "bg_removal":                {"cost": 3,   "usd": Decimal("0.020")},
    "product_scene":             {"cost": 10,  "usd": Decimal("0.040")},
    "product_scene_gen":         {"cost": 10,  "usd": Decimal("0.040")},
    "pattern_gen":               {"cost": 2,   "usd": Decimal("0.030")},
    "pattern_generate":          {"cost": 2,   "usd": Decimal("0.030")},
    "room_redesign":             {"cost": 20,  "usd": Decimal("0.040")},
    "i2i":                       {"cost": 2,   "usd": Decimal("0.030")},
    "image_transform":           {"cost": 2,   "usd": Decimal("0.030")},
    "image_translator":          {"cost": 2,   "usd": Decimal("0.030")},
    "image_translation":         {"cost": 2,   "usd": Decimal("0.030")},
    "style_transfer":            {"cost": 2,   "usd": Decimal("0.030")},

    # video
    "image_to_video":            {"cost": 20,  "usd": Decimal("0.150")},
    "text_to_video":             {"cost": 20,  "usd": Decimal("0.150")},
    "short_video":               {"cost": 20,  "usd": Decimal("0.150")},
    "video_generation_standard": {"cost": 20,  "usd": Decimal("0.150")},
    "video_generation_professional": {"cost": 60, "usd": Decimal("0.500")},

    # try-on / avatar / lip-sync — Kling try-on $0.50-1.00, A2E avatar $1-3
    "ai_try_on":                 {"cost": 30,  "usd": Decimal("0.700")},
    "try_on":                    {"cost": 30,  "usd": Decimal("0.700")},
    "virtual_try_on":            {"cost": 30,  "usd": Decimal("0.700")},
    "ai_avatar":                 {"cost": 80,  "usd": Decimal("2.000")},
    "avatar":                    {"cost": 80,  "usd": Decimal("2.000")},
    "lip_sync":                  {"cost": 50,  "usd": Decimal("1.000")},
    "video_dubbing":             {"cost": 60,  "usd": Decimal("1.500")},

    # extend / repair / upscale
    "video_extend":              {"cost": 30,  "usd": Decimal("0.500")},
    "video_transform":           {"cost": 30,  "usd": Decimal("0.500")},
    "video_background_remove":   {"cost": 50,  "usd": Decimal("0.300")},
    "image_upscale":             {"cost": 15,  "usd": Decimal("0.150")},
    "video_upscale":             {"cost": 50,  "usd": Decimal("0.500")},
    "upscale":                   {"cost": 15,  "usd": Decimal("0.150")},

    # interior / claymation / effect
    "interior_design":           {"cost": 2,   "usd": Decimal("0.030")},
    "effect":                    {"cost": 1,   "usd": Decimal("0.025")},
    "claymation":                {"cost": 50,  "usd": Decimal("0.350")},

    # effects_service.py hard-codes these credit_costs; align DB so the
    # admin dashboard's `margin_usd` reflects what's actually being charged.
    "vidgo_style":               {"cost": 8,   "usd": Decimal("0.150")},
    "vidgo_hd_enhance":          {"cost": 10,  "usd": Decimal("0.200")},
    "vidgo_video_pro":           {"cost": 30,  "usd": Decimal("0.250")},
}

# Rows brand-new in v2.2 (2026 PiAPI catalog additions). Include enough
# metadata that the deduction firewall + admin dashboard render correctly.
NEW_SERVICE_PRICING_INSERTS = [
    {
        "service_type": "nano_banana_pro_t2i",
        "display_name": "Nano Banana Pro (T2I)",
        "credit_cost": 5,
        "api_cost_usd": Decimal("0.100"),
        "model_type": "gemini_pro",
        "tool_category": "premium",
        "tool_type": "text_to_image",
        "resolution": "1024x1024",
        "max_duration": None,
        "subscribers_only": True,
        "min_plan": "pro",
        "allowed_models": ["gemini_pro"],
        "description": "Google Gemini Nano Banana Pro 高品質 T2I",
    },
    {
        "service_type": "seedream_5_lite_t2i",
        "display_name": "Seedream 5 Lite (T2I)",
        "credit_cost": 1,
        "api_cost_usd": Decimal("0.025")
        ,
        "model_type": "default",
        "tool_category": "dynamic",
        "tool_type": "text_to_image",
        "resolution": "1024x1024",
        "max_duration": None,
        "subscribers_only": False,
        "min_plan": "basic",
        "allowed_models": ["seedream"],
        "description": "ByteDance Seedream 5 Lite — 中低價位 T2I",
    },
    {
        "service_type": "hailuo_fast_video",
        "display_name": "Hailuo Fast 影片",
        "credit_cost": 20,
        "api_cost_usd": Decimal("0.100"),
        "model_type": "default",
        "tool_category": "dynamic",
        "tool_type": "image_to_video",
        "resolution": "720p",
        "max_duration": 5,
        "subscribers_only": True,
        "min_plan": "basic",
        "allowed_models": ["hailuo"],
        "description": "Hailuo Fast — 平價影片預設",
    },
    {
        "service_type": "kling_omni_video",
        "display_name": "Kling 3.0 Omni 影片",
        "credit_cost": 60,
        "api_cost_usd": Decimal("0.500"),
        "model_type": "wan_pro",
        "tool_category": "premium",
        "tool_type": "image_to_video",
        "resolution": "1080p",
        "max_duration": 10,
        "subscribers_only": True,
        "min_plan": "pro",
        "allowed_models": ["kling_omni"],
        "description": "Kling 3.0 Omni — 旗艦影片",
    },
    {
        "service_type": "hunyuan_video",
        "display_name": "Hunyuan 中文影片",
        "credit_cost": 25,
        "api_cost_usd": Decimal("0.300"),
        "model_type": "default",
        "tool_category": "dynamic",
        "tool_type": "image_to_video",
        "resolution": "720p",
        "max_duration": 5,
        "subscribers_only": True,
        "min_plan": "basic",
        "allowed_models": ["hunyuan"],
        "description": "Hunyuan — 中文 prompts 影片",
    },
]


# v2.2 pack values — heavy_pack rerated so packs no longer undercut subs.
NEW_PACK_VALUES = [
    {"name": "light_pack",    "credits": 250, "price_twd": Decimal("299"), "price_usd": Decimal("9.99")},
    {"name": "standard_pack", "credits": 450, "price_twd": Decimal("499"), "price_usd": Decimal("16.99")},
    {"name": "heavy_pack",    "credits": 850, "price_twd": Decimal("999"), "price_usd": Decimal("32.99")},
]

# v2.1 pack baseline (for downgrade).
OLD_PACK_VALUES = [
    {"name": "light_pack",    "credits": 250,  "price_twd": Decimal("299"), "price_usd": Decimal("9.99")},
    {"name": "standard_pack", "credits": 450,  "price_twd": Decimal("499"), "price_usd": Decimal("16.99")},
    {"name": "heavy_pack",    "credits": 1000, "price_twd": Decimal("999"), "price_usd": Decimal("32.99")},
]

# v2.1 prior service_pricing values (for downgrade). Only the rows v2.1
# explicitly set are listed — leave the rest untouched.
OLD_SERVICE_PRICING_VALUES = {
    "text_to_image_default":         {"cost": 1},
    "image_generation_default":      {"cost": 1},
    "image_generation_premium":      {"cost": 5},
    "short_video":                   {"cost": 20},
    "video_generation_standard":     {"cost": 20},
    "video_generation_professional": {"cost": 60},
    "image_upscale":                 {"cost": 15},
    "video_upscale":                 {"cost": 15},
}


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. Upsert per-feature credit_cost + api_cost_usd.
    # UPDATE first; if no row matches, INSERT a minimal row carrying just
    # service_type + credit_cost + api_cost_usd. The deduction firewall
    # reads credit_cost; other columns are nice-to-have for the dashboard.
    for service_type, row in NEW_SERVICE_PRICING_VALUES.items():
        result = bind.execute(
            sa.text("""
                UPDATE service_pricing
                   SET credit_cost  = :cost,
                       api_cost_usd = :usd,
                       updated_at   = NOW()
                 WHERE service_type = :service_type
            """),
            {"service_type": service_type, "cost": row["cost"], "usd": row["usd"]},
        )
        if result.rowcount == 0:
            bind.execute(
                sa.text("""
                    INSERT INTO service_pricing (
                        id, service_type, display_name, credit_cost, api_cost_usd,
                        model_type, tool_category, is_active, created_at, updated_at
                    )
                    VALUES (
                        CAST(:id AS UUID), :service_type, :display_name,
                        :cost, :usd, 'default', 'dynamic', TRUE, NOW(), NOW()
                    )
                    ON CONFLICT (service_type) DO UPDATE SET
                        credit_cost  = EXCLUDED.credit_cost,
                        api_cost_usd = EXCLUDED.api_cost_usd,
                        updated_at   = NOW()
                """),
                {
                    "id": str(uuid.uuid4()),
                    "service_type": service_type,
                    "display_name": service_type.replace("_", " ").title(),
                    "cost": row["cost"],
                    "usd": row["usd"],
                },
            )

    # ── 2. Insert v2.2 new-catalog rows.
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

    # ── 3. Rerate heavy_pack (close arbitrage). light/standard unchanged.
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


def downgrade() -> None:
    bind = op.get_bind()

    # Restore v2.1 pack values.
    for pack in OLD_PACK_VALUES:
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

    # Restore the v2.1 service_pricing values (only those v2.1 set).
    for service_type, row in OLD_SERVICE_PRICING_VALUES.items():
        bind.execute(
            sa.text("""
                UPDATE service_pricing
                   SET credit_cost = :cost,
                       updated_at  = NOW()
                 WHERE service_type = :service_type
            """),
            {"service_type": service_type, "cost": row["cost"]},
        )

    # Remove the v2.2 new-catalog rows.
    for row in NEW_SERVICE_PRICING_INSERTS:
        bind.execute(
            sa.text("DELETE FROM service_pricing WHERE service_type = :st"),
            {"st": row["service_type"]},
        )
