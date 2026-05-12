"""Hero demo pair mapping table

Revision ID: a2b3c4d5e6f7
Revises: z1a2b3c4d5e6
Create Date: 2026-05-12

Backs the landing-page hero demo. Previously the BEFORE/AFTER pair was
read from the generic Material catalogue with a hard-coded FALLBACK in
LandingPage.vue that overrode known-bad seeds. That hack kept failing
whenever a new seed slipped past the regex (e.g. the Studio Scene tab
showed a tall bubble-tea cup BEFORE and a squat cup AFTER because the
seeded result was a re-imagined product, not a re-scened one).

This table is the single source of truth for the hero pair, populated
by the admin /admin/hero/regenerate endpoint which uses Gemini 2.5
Flash Image to render the AFTER from the BEFORE while preserving the
subject's exact silhouette. Frontend reads from /hero/pairs.

One row per (tool_type, slug). slug lets us keep multiple variants of
the same tool (e.g. bubble tea + coffee for product_scene) without a
separate table per product.
"""
from alembic import op
import sqlalchemy as sa


revision = "a2b3c4d5e6f7"
down_revision = "z1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hero_demo_pairs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tool_type", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("before_url", sa.Text(), nullable=False),
        sa.Column("after_url", sa.Text(), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("label_en", sa.String(length=120), nullable=True),
        sa.Column("label_zh", sa.String(length=120), nullable=True),
        sa.Column(
            "display_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.UniqueConstraint("tool_type", "slug", name="uq_hero_demo_pair_tool_slug"),
    )
    op.create_index(
        "ix_hero_demo_pairs_tool_type",
        "hero_demo_pairs",
        ["tool_type"],
    )

    # Seed the five hero rotation slots with the BEFORE URLs the
    # LandingPage already references, the canonical scene prompt for
    # each tool, and a NULL after_url. The admin endpoint produces the
    # AFTER on first call (or we can backfill manually from a one-off
    # script) so a freshly-deployed environment doesn't render a stale
    # AI Avatar / Studio Scene demo from the legacy Material rows.
    op.execute(
        """
        INSERT INTO hero_demo_pairs
          (tool_type, slug, before_url, prompt, label_en, label_zh, display_order)
        VALUES
          (
            'product_scene', 'bubbletea',
            'https://storage.googleapis.com/vidgo-media-vidgo-ai/examples/bg/bubbletea.png',
            'Place this exact bubble milk tea cup on a soft pastel marble studio backdrop. Overhead studio softbox lighting. The cup must keep its original tall slim silhouette, lid, straw, bubble pattern, and liquid color EXACTLY — do not change the cup shape, do not invent a different cup. Photorealistic commercial product photography, sharp focus, balanced exposure, no text, no people.',
            'Studio Scene', '商品情境',
            0
          ),
          (
            'background_removal', 'bubbletea',
            'https://storage.googleapis.com/vidgo-media-vidgo-ai/examples/bg/bubbletea.png',
            'Remove the background from this bubble milk tea cup. Output a clean transparent-background PNG with crisp edges; preserve the cup, straw, lid, foam, and bubble pattern EXACTLY. No fringing, no halo, no recoloring.',
            'Cutout', '商品去背',
            0
          ),
          (
            'try_on', 'garment-tshirt',
            'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/try-on/garment-tshirt-only.png',
            'Place this exact t-shirt garment onto a neutral fashion-studio female model. Preserve the t-shirt color, fabric, pattern, sleeve length, neckline, and print EXACTLY. Soft studio lighting, plain backdrop, natural fit, no logos invented, no extra accessories.',
            'Try-On', '模特試穿',
            0
          ),
          (
            'room_redesign', 'living-modern',
            'https://storage.googleapis.com/vidgo-media-vidgo-ai/examples/room/living-room.png',
            'Redesign this living room in warm Japandi style. PRESERVE the exact walls, window positions, ceiling height, floor plan, and overall room footprint. Empty staged interior — no people, no pets. Photorealistic real-estate interior photography.',
            'Room', '室內設計',
            0
          ),
          (
            'short_video', 'bubbletea',
            'https://storage.googleapis.com/vidgo-media-vidgo-ai/examples/bg/bubbletea.png',
            'First-frame still for an image-to-video clip of this bubble milk tea cup. Cinematic café hero shot, subtle camera push-in suggested. Keep the cup silhouette, color, and bubble pattern EXACTLY.',
            'Short Video', '商品短影音',
            0
          )
        ON CONFLICT (tool_type, slug) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_hero_demo_pairs_tool_type", table_name="hero_demo_pairs")
    op.drop_table("hero_demo_pairs")
