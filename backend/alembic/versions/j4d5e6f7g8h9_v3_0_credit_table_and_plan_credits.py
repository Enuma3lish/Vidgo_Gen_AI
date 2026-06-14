"""VidGo 3.0 — per-model 扣點表 + 方案金額 (2026-06 pricing spec).

Revision ID: j4d5e6f7g8h9
Revises: i3c4d5e6f7g8
Create Date: 2026-06-08

Implements the 2026-06 "扣點表 + 方案金額" spec. Iron rule: every task sells for
≥2.5× upstream cost at 1 credit = US$0.04 → credits = ceil(piapi_usd/0.04*2.5).

  * Video is charged PER model + resolution (no single fixed value): Hailuo 18,
    Wan 20, Hunyuan 20, Kling V2.5 STD 28, Seedance 720p 65 / 1080p 160,
    Kling V3.0 STD 65 / PRO 130, Veo 80, Sora2 80.
  * Image: standard 2, premium edit 3, nano-banana 1K 8 / 4K 12, upscale 3,
    background removal 2.
  * Subscription monthly credits cut to hold ≥US$0.044/credit: basic 450→400,
    pro 1200→1000, premium 2200→1800. TWD/ECPay subscribers get a smaller
    allowance (350/900/1600) via the new plans.monthly_credits_twd column so the
    cheaper NT$ price can't be arbitraged against the USD plan. Premium NT$
    price 1699→1799.
  * Credit packs restored to the $0.04 floor: standard_pack 450→416,
    heavy_pack 850→833 (light_pack 250 unchanged).

Mirrors app/services/tier_config.py (VIDEO_CREDIT_COSTS / IMAGE_CREDIT_COSTS) —
keep the two in lockstep. Upgrade is idempotent.
"""
import json
import uuid
from decimal import Decimal
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j4d5e6f7g8h9"
down_revision: Union[str, None] = "i3c4d5e6f7g8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# service_type -> (credit_cost, api_cost_usd, model_type, tool_category,
#                  tool_type, resolution, max_duration, display_name)
SERVICE_ROWS = {
    # ---- image ----
    "text_to_image":            (2,  "0.015", "default",    "static",  "text_to_image",     "1024x1024", None, "Standard AI image (Z-Image/Qwen)"),
    "image_generation_premium": (3,  "0.025", "premium",    "premium", "text_to_image",     "1024x1024", None, "Premium image (Flux dev / Qwen edit)"),
    "nano_banana_t2i":          (8,  "0.105", "gemini_pro", "premium", "text_to_image",     "1024x1024", None, "Gemini / nano-banana 1K"),
    "nano_banana_4k_t2i":       (12, "0.18",  "gemini_pro", "premium", "text_to_image",     "4096x4096", None, "nano-banana 4K"),
    "image_upscale":            (3,  "0.005", "default",    "static",  "image_upscale",     None,        None, "Upscale"),
    "upscale":                  (3,  "0.005", "default",    "static",  "image_upscale",     None,        None, "Upscale"),
    "bg_removal":               (2,  "0.001", "default",    "static",  "background_removal", None,       None, "Background Removal"),
    "background_removal":       (2,  "0.001", "default",    "static",  "background_removal", None,       None, "Background Removal"),
    # ---- video (per model + resolution) ----
    "video_hailuo":         (18,  "0.26", "default", "dynamic", "image_to_video", "768p",  10, "Hailuo Fast 10s 768p"),
    "video_wan":            (20,  "0.28", "default", "dynamic", "image_to_video", "480p",  5,  "Wan 480p"),
    "video_hunyuan":        (20,  "0.28", "default", "dynamic", "image_to_video", "720p",  5,  "Hunyuan"),
    "video_kling_std":      (28,  "0.40", "wan_pro", "premium", "image_to_video", "720p",  10, "Kling V2.5 STD 10s"),
    "video_seedance_720p":  (65,  "1.00", "wan_pro", "premium", "image_to_video", "720p",  5,  "Seedance 720p 5s"),
    "video_seedance_1080p": (160, "2.50", "wan_pro", "premium", "image_to_video", "1080p", 5,  "Seedance 1080p 5s"),
    "video_kling_v3_std":   (65,  "1.00", "wan_pro", "premium", "image_to_video", "1080p", 10, "Kling V3.0 STD 10s"),
    "video_kling_v3_pro":   (130, "2.00", "veo",     "premium", "image_to_video", "1080p", 10, "Kling V3.0 PRO 10s (audio)"),
    "video_veo":            (80,  "1.20", "veo",     "premium", "image_to_video", "1080p", 5,  "Veo 3.1 5s (audio)"),
    "video_sora2":          (80,  "1.20", "veo",     "premium", "image_to_video", "1080p", 5,  "Sora2 Pro 5s"),
}

# Legacy video service_types kept for any lingering references — repriced to the
# new floor so they can't over/under-charge against the new table.
LEGACY_REPRICE = {
    "short_video": 18, "image_to_video": 18, "text_to_video": 18,
    "seedance_wan_video": 20, "video_generation_professional": 28,
    "video_flagship": 65, "video_kling_omni": 130, "veo3_video": 80,
}

# name, monthly_credits, monthly_credits_twd, price_twd, price_monthly, price_yearly
PLAN_UPDATES = [
    ("basic",   400,  350,  None,            None,   None),
    ("pro",     1000, 900,  None,            None,   None),
    ("premium", 1800, 1600, Decimal("1799"), 1799.0, 17990.0),
]

PACK_UPDATES = [("standard_pack", 416), ("heavy_pack", 833)]


def _upsert_service_row(bind, service_type, row):
    cost, usd, model_type, tool_category, tool_type, resolution, max_duration, display_name = row
    result = bind.execute(
        sa.text("""
            UPDATE service_pricing
               SET credit_cost = :cost, api_cost_usd = :usd, model_type = :model_type,
                   tool_category = :tool_category, tool_type = :tool_type,
                   resolution = :resolution, max_duration = :max_duration,
                   display_name = :display_name, is_active = TRUE, updated_at = NOW()
             WHERE service_type = :service_type
        """),
        {"service_type": service_type, "cost": cost, "usd": Decimal(usd),
         "model_type": model_type, "tool_category": tool_category, "tool_type": tool_type,
         "resolution": resolution, "max_duration": max_duration, "display_name": display_name},
    )
    if result.rowcount == 0:
        bind.execute(
            sa.text("""
                INSERT INTO service_pricing (
                    id, service_type, display_name, credit_cost, api_cost_usd,
                    model_type, tool_category, tool_type, resolution, max_duration,
                    allowed_models, is_active, created_at, updated_at
                ) VALUES (
                    CAST(:id AS UUID), :service_type, :display_name, :cost, :usd,
                    :model_type, :tool_category, :tool_type, :resolution, :max_duration,
                    CAST(:allowed_models AS JSON), TRUE, NOW(), NOW()
                )
                ON CONFLICT (service_type) DO UPDATE SET
                    credit_cost = EXCLUDED.credit_cost, api_cost_usd = EXCLUDED.api_cost_usd,
                    model_type = EXCLUDED.model_type, tool_category = EXCLUDED.tool_category,
                    tool_type = EXCLUDED.tool_type, resolution = EXCLUDED.resolution,
                    max_duration = EXCLUDED.max_duration, display_name = EXCLUDED.display_name,
                    is_active = TRUE, updated_at = NOW()
            """),
            {"id": str(uuid.uuid4()), "service_type": service_type, "display_name": display_name,
             "cost": cost, "usd": Decimal(usd), "model_type": model_type,
             "tool_category": tool_category, "tool_type": tool_type, "resolution": resolution,
             "max_duration": max_duration, "allowed_models": json.dumps(["default"])},
        )


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. Add plans.monthly_credits_twd (idempotent).
    cols = [c["name"] for c in sa.inspect(bind).get_columns("plans")]
    if "monthly_credits_twd" not in cols:
        op.add_column("plans", sa.Column("monthly_credits_twd", sa.Integer(), nullable=True))

    # ── 2. Per-model 扣點表 rows.
    for service_type, row in SERVICE_ROWS.items():
        _upsert_service_row(bind, service_type, row)
    for service_type, cost in LEGACY_REPRICE.items():
        bind.execute(
            sa.text("UPDATE service_pricing SET credit_cost = :cost, updated_at = NOW() WHERE service_type = :st"),
            {"cost": cost, "st": service_type},
        )

    # ── 3. Subscription plan credits (USD + TWD) and Premium NT$ price.
    for name, credits, credits_twd, price_twd, price_monthly, price_yearly in PLAN_UPDATES:
        sets = ["monthly_credits = :credits", "monthly_credits_twd = :credits_twd", "updated_at = NOW()"]
        params = {"name": name, "credits": credits, "credits_twd": credits_twd}
        if price_twd is not None:
            sets += ["price_twd = :price_twd", "price_monthly = :price_monthly", "price_yearly = :price_yearly"]
            params.update({"price_twd": price_twd, "price_monthly": price_monthly, "price_yearly": price_yearly})
        bind.execute(sa.text(f"UPDATE plans SET {', '.join(sets)} WHERE name = :name"), params)

    # ── 4. Credit packs back to the $0.04 floor.
    for name, credits in PACK_UPDATES:
        bind.execute(
            sa.text("UPDATE credit_packages SET credits = :credits, updated_at = NOW() WHERE name = :name"),
            {"credits": credits, "name": name},
        )


def downgrade() -> None:
    bind = op.get_bind()

    # Restore v2.2 plan credits + Premium NT$ price.
    for name, credits, price_twd, price_monthly, price_yearly in [
        ("basic", 450, None, None, None),
        ("pro", 1200, None, None, None),
        ("premium", 2200, Decimal("1699"), 1699.0, 16990.0),
    ]:
        sets = ["monthly_credits = :credits", "updated_at = NOW()"]
        params = {"name": name, "credits": credits}
        if price_twd is not None:
            sets += ["price_twd = :price_twd", "price_monthly = :price_monthly", "price_yearly = :price_yearly"]
            params.update({"price_twd": price_twd, "price_monthly": price_monthly, "price_yearly": price_yearly})
        bind.execute(sa.text(f"UPDATE plans SET {', '.join(sets)} WHERE name = :name"), params)

    # Restore v2.2 pack credits.
    for name, credits in [("standard_pack", 450), ("heavy_pack", 850)]:
        bind.execute(
            sa.text("UPDATE credit_packages SET credits = :credits, updated_at = NOW() WHERE name = :name"),
            {"credits": credits, "name": name},
        )

    # Restore the v2.2 service_pricing values that v3.0 changed.
    for service_type, cost in {
        "text_to_image": 1, "image_generation_premium": 5, "bg_removal": 3,
        "background_removal": 3, "image_upscale": 15, "upscale": 15,
        "short_video": 20, "image_to_video": 20, "text_to_video": 20,
        "seedance_wan_video": 40, "video_generation_professional": 60,
        "video_flagship": 500, "video_kling_omni": 750, "veo3_video": 200,
    }.items():
        bind.execute(
            sa.text("UPDATE service_pricing SET credit_cost = :cost, updated_at = NOW() WHERE service_type = :st"),
            {"cost": cost, "st": service_type},
        )

    # Remove the v3.0 per-model rows that didn't exist before.
    for service_type in [
        "nano_banana_4k_t2i", "video_hailuo", "video_wan", "video_hunyuan",
        "video_kling_std", "video_seedance_720p", "video_seedance_1080p",
        "video_kling_v3_std", "video_kling_v3_pro", "video_veo", "video_sora2",
    ]:
        bind.execute(sa.text("DELETE FROM service_pricing WHERE service_type = :st"), {"st": service_type})

    cols = [c["name"] for c in sa.inspect(bind).get_columns("plans")]
    if "monthly_credits_twd" in cols:
        op.drop_column("plans", "monthly_credits_twd")
