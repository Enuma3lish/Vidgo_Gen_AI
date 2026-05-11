"""Admin-editable branding + plan copy: site_settings table, plan features_text & display_order

Revision ID: z1a2b3c4d5e6
Revises: y9z0a1b2c3d4, 1bb965787d97
Create Date: 2026-05-11

Adds the infrastructure required by the new admin pages:

1. `site_settings` (singleton, id=1) — admin-editable logo URLs, brand name /
   tagline, and the bilingual pricing-page intro / footnote copy. Letting the
   admin edit this in the panel removes the need to redeploy the frontend
   each time the pricing-page copy or logo changes.

2. `plans.features_text_zh` / `plans.features_text_en` — long-form bilingual
   feature list shown on the pricing card. One bullet per line.

3. `plans.display_order` — explicit sort key on the pricing grid so admins
   can reorder cards without touching prices.

The migration also seeds a single empty row in `site_settings` so the GET
endpoint always returns something, and the admin UI can immediately PATCH
fields without the backend needing to handle "row does not exist yet".

This migration merges the two heads `y9z0a1b2c3d4` and `1bb965787d97` that
existed before this revision.
"""
from alembic import op
import sqlalchemy as sa


revision = 'z1a2b3c4d5e6'
down_revision = ('y9z0a1b2c3d4', '1bb965787d97')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- site_settings ----
    op.create_table(
        'site_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('logo_url', sa.Text(), nullable=True),
        sa.Column('logo_url_dark', sa.Text(), nullable=True),
        sa.Column('favicon_url', sa.Text(), nullable=True),
        sa.Column('brand_name', sa.String(length=120), nullable=True),
        sa.Column('brand_tagline_zh', sa.Text(), nullable=True),
        sa.Column('brand_tagline_en', sa.Text(), nullable=True),
        sa.Column('pricing_intro_title_zh', sa.String(length=200), nullable=True),
        sa.Column('pricing_intro_title_en', sa.String(length=200), nullable=True),
        sa.Column('pricing_intro_body_zh', sa.Text(), nullable=True),
        sa.Column('pricing_intro_body_en', sa.Text(), nullable=True),
        sa.Column('pricing_footnote_zh', sa.Text(), nullable=True),
        sa.Column('pricing_footnote_en', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Seed the singleton row so the GET endpoint always has data to return.
    op.execute("INSERT INTO site_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING")

    # ---- plans extension ----
    bind = op.get_bind()
    existing = {
        row[0] for row in bind.exec_driver_sql(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'plans'"
        ).fetchall()
    }
    if 'features_text_zh' not in existing:
        op.add_column('plans', sa.Column('features_text_zh', sa.Text(), nullable=True))
    if 'features_text_en' not in existing:
        op.add_column('plans', sa.Column('features_text_en', sa.Text(), nullable=True))
    if 'display_order' not in existing:
        op.add_column('plans', sa.Column('display_order', sa.Integer(), nullable=True))


def downgrade() -> None:
    # Drop only the columns/tables we created.
    bind = op.get_bind()
    existing = {
        row[0] for row in bind.exec_driver_sql(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'plans'"
        ).fetchall()
    }
    if 'display_order' in existing:
        op.drop_column('plans', 'display_order')
    if 'features_text_en' in existing:
        op.drop_column('plans', 'features_text_en')
    if 'features_text_zh' in existing:
        op.drop_column('plans', 'features_text_zh')

    op.drop_table('site_settings')
