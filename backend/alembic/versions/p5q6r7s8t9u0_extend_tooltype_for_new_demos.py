"""Add 5 new ToolType enum values for the empty-gallery tool pages.

Revision ID: p5q6r7s8t9u0
Revises: o4p5q6r7s8t9
Create Date: 2026-05-26

Background
----------
The demo system rejected /demo/presets/<tool_type> requests for 5 tools
(claymation, kling_video, upscale, image_translator, midjourney_imagine)
because they were never added to the `tooltype` Postgres enum nor to
the `topic_registry`. Result: those tool pages rendered empty
ExampleGalleries (no demo, no learn-by-example) since the day they
shipped.

Owner directive (2026-05-26 audit): close the gap so every tool has
≥ 3 example presets visible in production.

What this migration does
------------------------
ALTER TYPE tooltype ADD VALUE for each of the 5 new strings.

Postgres specifics
------------------
`ALTER TYPE ... ADD VALUE` MUST run outside any transaction. Alembic
wraps every migration in a transaction by default; the workaround is
calling `commit()` on the connection before each ADD VALUE so each
ALTER lives in its own implicit txn. We also wrap with IF NOT EXISTS
so the migration is idempotent — running it a second time is a no-op
and won't crash on already-present values.

Downgrade
---------
PostgreSQL has NO native way to remove an enum value. The downgrade
intentionally fails loudly rather than pretending — operators would
need to drop+recreate the type, which would require updating every
row that references the value being removed. Don't downgrade unless
the rows using these values have been migrated to other values first.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text  # SQLAlchemy 2.x: raw SQL must be wrapped


revision: str = "p5q6r7s8t9u0"
down_revision: Union[str, None] = "o4p5q6r7s8t9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_TOOL_TYPES = (
    "claymation",
    "kling_video",
    "upscale",
    "image_translator",
    "midjourney_imagine",
)


def upgrade() -> None:
    # ALTER TYPE ADD VALUE must be outside a transaction. Commit the
    # implicit one Alembic opened, then run each ADD VALUE standalone.
    # SQLAlchemy 2.x: raw SQL must be wrapped in text() — passing a bare
    # string raises ObjectNotExecutableError.
    conn = op.get_bind()
    conn.execute(text("COMMIT"))
    for value in NEW_TOOL_TYPES:
        # IF NOT EXISTS makes this idempotent — safe to re-run.
        conn.execute(text(f"ALTER TYPE tooltype ADD VALUE IF NOT EXISTS '{value}'"))


def downgrade() -> None:
    raise NotImplementedError(
        "PostgreSQL does not support removing enum values without recreating "
        "the type. To remove these values, first migrate every Material / "
        "UserGeneration row using the value to a different tool_type, then "
        "manually DROP TYPE tooltype CASCADE + CREATE TYPE tooltype AS ENUM "
        "(...) with the desired set, then re-add the column references."
    )
