"""Add 'sora2' to the tooltype enum so Sora 2 Pro renders save to the gallery.

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-06-16

Background
----------
`/tools/sora2-pro` (_sora2_pro_inner) returned the generated video to the
client but never wrote a UserGeneration row, so Sora 2 results never appeared
in the user's "My Works" gallery. The fix persists a UserGeneration with
tool_type=ToolType.SORA2 — which requires the value to exist in the Postgres
`tooltype` enum first.

Postgres specifics
------------------
`ALTER TYPE ... ADD VALUE` MUST run outside a transaction. Alembic wraps every
migration in one, so we COMMIT the implicit transaction first, then run the
ADD VALUE standalone. IF NOT EXISTS makes it idempotent. Mirrors
p5q6r7s8t9u0_extend_tooltype_for_new_demos.py.

Downgrade
---------
PostgreSQL cannot remove an enum value without recreating the type; the
downgrade intentionally raises rather than pretend.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("COMMIT"))
    conn.execute(text("ALTER TYPE tooltype ADD VALUE IF NOT EXISTS 'sora2'"))


def downgrade() -> None:
    raise NotImplementedError(
        "PostgreSQL does not support removing enum values without recreating "
        "the type. Migrate any UserGeneration row with tool_type='sora2' to a "
        "different value first."
    )
