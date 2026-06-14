"""Merge the two dangling heads (cohort branch + hero_pair_tryon_url_fix branch)

Revision ID: d6e7f8a9b0c1
Revises: b3c4d5e6f7a8, c5d6e7f8a9b0
Create Date: 2026-05-14

`alembic upgrade head` fails at container startup with "Multiple head
revisions are present" because two parallel heads exist:

- b3c4d5e6f7a8 (hero_pair_tryon_url_fix) — sat on its own since 2026-05-12,
  never merged after its sibling chain (m1e2r3g4h5i6 + later) advanced.
- c5d6e7f8a9b0 (add_cohort_to_generation_metrics) — current model-registry
  branch tip.

This is a no-op merge migration: just declares both heads as the parents of
a new single head so the linear `alembic upgrade head` resolves.
"""
from alembic import op  # noqa: F401


revision = 'd6e7f8a9b0c1'
down_revision = ('b3c4d5e6f7a8', 'c5d6e7f8a9b0')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
