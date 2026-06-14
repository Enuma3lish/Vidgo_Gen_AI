"""Merge two heads: g1a2b3c4d5e6 (v2.1 pricing rollout) + m2n3o4p5q6r7 (plan i18n)

Revision ID: n3o4p5q6r7s8
Revises: g1a2b3c4d5e6, m2n3o4p5q6r7
Create Date: 2026-05-24

Both branches modify `plans`:
  - g1a2b3c4d5e6_v2_1_pricing_rollout — v2.1 pricing tier rollout
  - m2n3o4p5q6r7_add_plan_bilingual_display_columns — display_name_zh/en
    + description_zh/en (today's QA fix)

This merge gives Alembic a single head so `alembic upgrade head` runs
cleanly at container startup. No schema change here — just the merge.

Why a merge is needed (post-mortem 2026-05-24):
  - My new migration set down_revision='e7f8a9b0c1d2' (payment_settings).
  - But `g1a2b3c4d5e6_v2_1_pricing_rollout` was also a dangling head,
    descended from f1a2b3c4d5e6, NOT from e7f8a9b0c1d2.
  - Two unmerged heads → `alembic upgrade head` (singular) refused to
    run → backend container exits → Cloud Run health check timeout →
    deploy rolls back.
  - This is the third "dangling heads" merge in this repo (see
    `d6e7f8a9b0c1_merge_cohort_and_hero_pair` and the merge baked into
    `z1a2b3c4d5e6_admin_branding_and_plan_copy.down_revision`). Keeping
    a single head requires conscious effort whenever multiple PRs add
    migrations in parallel.
"""
from alembic import op  # noqa: F401  (kept for symmetry; no DDL emitted)
import sqlalchemy as sa  # noqa: F401


revision = 'n3o4p5q6r7s8'
down_revision = ('g1a2b3c4d5e6', 'm2n3o4p5q6r7')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
