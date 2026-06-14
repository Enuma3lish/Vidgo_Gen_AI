"""Bilingual plan display copy — adds display_name_zh/en + description_zh/en

Revision ID: m2n3o4p5q6r7
Revises: e7f8a9b0c1d2
Create Date: 2026-05-24

QA report: "the i18n doesn't [work] on pricing page" when admin edits the
plan display_name + description in only one language. Mirroring the
existing features_text_zh/en split pattern, this migration adds four
nullable columns to the `plans` table:

  - display_name_zh / display_name_en
  - description_zh / description_en

Pricing.vue will prefer the locale-matched column at render time and
fall back to the existing single-locale `display_name` / `description`
when the new field is NULL — so this migration is non-destructive and
plans seeded before today keep working.

NOTE on revision IDs:
- The first draft of this file accidentally reused `a1b2c3d4e5f6`, which
  is already taken by `add_demo_usage_tracking`. Prod failed to start
  with "Cycle is detected in revisions" 2026-05-24. The current ID
  `m2n3o4p5q6r7` is unused across the existing tree.
- `down_revision = e7f8a9b0c1d2` (the most recent linear head — see git
  log "15db18e fix(alembic): merge dangling heads" + the subsequent
  `e7f8a9b0c1d2_add_payment_settings`). Picking the latest head keeps
  this migration off any side branches.
"""
from alembic import op
import sqlalchemy as sa


revision = 'm2n3o4p5q6r7'
down_revision = 'e7f8a9b0c1d2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('plans', sa.Column('display_name_zh', sa.String(length=100), nullable=True))
    op.add_column('plans', sa.Column('display_name_en', sa.String(length=100), nullable=True))
    op.add_column('plans', sa.Column('description_zh',  sa.String(),           nullable=True))
    op.add_column('plans', sa.Column('description_en',  sa.String(),           nullable=True))


def downgrade() -> None:
    op.drop_column('plans', 'description_en')
    op.drop_column('plans', 'description_zh')
    op.drop_column('plans', 'display_name_en')
    op.drop_column('plans', 'display_name_zh')
