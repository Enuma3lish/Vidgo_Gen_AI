"""merge watermark + invoice-mode alembic heads

Revision ID: b1c2d3e4f5a6
Revises: a1c2w3m4k5r6, e2f3g4h5i6j7
Create Date: 2026-06-16

The 2026-06 work left TWO alembic heads:
  - a1c2w3m4k5r6  (site_settings watermark fields)
  - e2f3g4h5i6j7  (users invoice-mode / B2B prefs)
The container entrypoint runs `alembic upgrade head`, which errors with
"Multiple head revisions are present" and exit(1) → the Cloud Run revision
cannot start. This empty merge unifies both into a single head so `head` is
unambiguous again. Both merged branches use `ADD COLUMN IF NOT EXISTS`, so
replaying them against a DB where the columns already exist is a no-op (see the
repo's idempotent-migration convention in docs/DEPLOYMENT_GUIDE.md).
"""
from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401


revision = 'b1c2d3e4f5a6'
down_revision = ('a1c2w3m4k5r6', 'e2f3g4h5i6j7')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Topology-only merge — no schema changes.
    pass


def downgrade() -> None:
    pass
