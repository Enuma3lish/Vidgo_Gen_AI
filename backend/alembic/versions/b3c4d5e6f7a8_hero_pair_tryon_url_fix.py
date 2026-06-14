"""Fix hero demo pair try_on before_url 403 + remove dead garment-tshirt seed

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-05-12

The seed in `a2b3c4d5e6f7` pointed try_on/garment-tshirt at
`static/try-on/garment-tshirt-only.png`, which is not a public path in
the bucket and returned 403 when the admin regen endpoint tried to
fetch it. Swap the row to the known-good
`static/tryon/garments/garment-coat.png` URL (already used by
LandingPage's FALLBACK.try_on.before for years) so the regeneration
endpoint can read it and produce a real model-wearing-the-coat AFTER.

slug also bumped to `garment-coat` so the row identifier matches what's
actually rendered.
"""
from alembic import op


revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE hero_demo_pairs
           SET slug = 'garment-coat',
               before_url = 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/tryon/garments/garment-coat.png',
               prompt = 'Place this exact coat garment onto a neutral fashion-studio female model. Preserve the coat color, fabric, pattern, cut, sleeve length, lapel shape, and trim EXACTLY. Soft studio lighting, plain backdrop, natural fit, no logos invented, no extra accessories.',
               after_url = NULL,
               generated_at = NULL
         WHERE tool_type = 'try_on' AND slug = 'garment-tshirt'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE hero_demo_pairs
           SET slug = 'garment-tshirt',
               before_url = 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/try-on/garment-tshirt-only.png'
         WHERE tool_type = 'try_on' AND slug = 'garment-coat'
        """
    )
