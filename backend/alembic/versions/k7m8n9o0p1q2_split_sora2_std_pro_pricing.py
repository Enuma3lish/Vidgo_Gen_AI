"""Split Sora 2 into std / pro billing rows (2026-07-12 SKU split).

Revision ID: k7m8n9o0p1q2
Revises: j4d5e6f7g8h9
Create Date: 2026-07-12

Sora 2 has two upstream tasks at PiAPI: ``sora2-video`` (std, $0.08/s, no audio)
and ``sora2-pro-video`` (pro, $0.24/s, synced audio). Until this migration we
billed both at 80 credits via the single ``video_sora2`` row, which meant any
user who picked std subsidised pro at the sub-billing layer (only Pro delivered
the ~2.2× margin doc target; std silently ran ~6.6× — Pro users effectively
subsidised anything std could have been). Split so pricing tracks upstream.

Adds ``video_sora2_std`` at 30 credits / $0.40 upstream / no audio. Leaves the
existing ``video_sora2`` row unchanged (kept as the Pro SKU for back-compat
with analytics history and the frontend's existing tool_type binding).

Mirrors app/services/tier_config.py VIDEO_CREDIT_COSTS["sora2_std"]. Upgrade
is idempotent (safe to re-run).
"""
import json
import uuid
from decimal import Decimal
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k7m8n9o0p1q2"
down_revision: Union[str, None] = "j4d5e6f7g8h9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SORA2_STD_ROW = {
    "service_type":  "video_sora2_std",
    "credit_cost":   30,
    "api_cost_usd":  Decimal("0.40"),
    "model_type":    "wan_pro",         # matches Kling V3.0 STD tier bucket
    "tool_category": "premium",
    "tool_type":     "image_to_video",
    "resolution":    "1080p",
    "max_duration":  5,
    "display_name":  "Sora2 STD 5s",
}


def upgrade() -> None:
    bind = op.get_bind()

    # UPSERT the new row. Same idempotency pattern the v3.0 migration used —
    # UPDATE first (0 rows if absent), else INSERT with ON CONFLICT.
    result = bind.execute(
        sa.text("""
            UPDATE service_pricing
               SET credit_cost = :credit_cost,
                   api_cost_usd = :api_cost_usd,
                   model_type = :model_type,
                   tool_category = :tool_category,
                   tool_type = :tool_type,
                   resolution = :resolution,
                   max_duration = :max_duration,
                   display_name = :display_name,
                   is_active = TRUE,
                   updated_at = NOW()
             WHERE service_type = :service_type
        """),
        _SORA2_STD_ROW,
    )
    if result.rowcount == 0:
        bind.execute(
            sa.text("""
                INSERT INTO service_pricing (
                    id, service_type, display_name, credit_cost, api_cost_usd,
                    model_type, tool_category, tool_type, resolution, max_duration,
                    allowed_models, is_active, created_at, updated_at
                ) VALUES (
                    CAST(:id AS UUID), :service_type, :display_name, :credit_cost, :api_cost_usd,
                    :model_type, :tool_category, :tool_type, :resolution, :max_duration,
                    CAST(:allowed_models AS JSON), TRUE, NOW(), NOW()
                )
                ON CONFLICT (service_type) DO UPDATE SET
                    credit_cost = EXCLUDED.credit_cost,
                    api_cost_usd = EXCLUDED.api_cost_usd,
                    model_type = EXCLUDED.model_type,
                    tool_category = EXCLUDED.tool_category,
                    tool_type = EXCLUDED.tool_type,
                    resolution = EXCLUDED.resolution,
                    max_duration = EXCLUDED.max_duration,
                    display_name = EXCLUDED.display_name,
                    is_active = TRUE,
                    updated_at = NOW()
            """),
            {
                **_SORA2_STD_ROW,
                "id": str(uuid.uuid4()),
                "allowed_models": json.dumps(["sora2_std", "sora-2-std"]),
            },
        )


def downgrade() -> None:
    # Deactivate rather than DELETE so historical charges keep referential
    # integrity if any usage rows were persisted with this service_type.
    op.execute("""
        UPDATE service_pricing
           SET is_active = FALSE, updated_at = NOW()
         WHERE service_type = 'video_sora2_std'
    """)
