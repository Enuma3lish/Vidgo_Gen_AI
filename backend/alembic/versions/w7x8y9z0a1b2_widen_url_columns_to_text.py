"""Widen URL columns to TEXT to fit signed GCS URLs (>500 chars)

Revision ID: w7x8y9z0a1b2
Revises: 99d728708134, n2b3c4d5e6f7, m1e2r3g4h5i6
Create Date: 2026-05-07

Signed Cloud Storage v4 URLs routinely exceed 1500 characters, but several
URL columns were declared as VARCHAR(500). When a tool endpoint records the
generation under the `materials` table (or related tables) using the
caller-supplied input URL, asyncpg raises StringDataRightTruncationError and
the request 500s (we observed this on /api/v1/tools/try-on when garment
images came from signed GCS URLs).

This migration converts every URL-bearing column to TEXT. PostgreSQL's
ALTER COLUMN ... TYPE TEXT on a VARCHAR is a metadata-only operation in 13+
when there is no USING clause, so it runs in milliseconds even on large
tables.
"""
from alembic import op


revision = 'w7x8y9z0a1b2'
down_revision = ('99d728708134', 'n2b3c4d5e6f7', 'm1e2r3g4h5i6')
branch_labels = None
depends_on = None


# (table, column) pairs that hold media URLs.
URL_COLUMNS = [
    ('materials', 'input_image_url'),
    ('materials', 'input_video_url'),
    ('materials', 'result_image_url'),
    ('materials', 'result_video_url'),
    ('materials', 'result_thumbnail_url'),
    ('materials', 'result_watermarked_url'),
    ('generations', 'input_image_url'),
    ('generations', 'image_url'),
    ('generations', 'video_url'),
    ('generations', 'thumbnail_url'),
    ('prompt_templates', 'input_image_url'),
    ('prompt_templates', 'input_video_url'),
    ('prompt_templates', 'result_image_url'),
    ('prompt_templates', 'result_video_url'),
    ('prompt_templates', 'result_thumbnail_url'),
    ('prompt_templates', 'result_watermarked_url'),
    ('demo_examples', 'image_url_before'),
    ('demo_examples', 'image_url_after'),
    ('demo_examples', 'thumbnail_url'),
    ('demo_videos', 'image_url'),
    ('demo_videos', 'video_url'),
]


def upgrade() -> None:
    bind = op.get_bind()
    for table, column in URL_COLUMNS:
        # Guard each ALTER so the migration is idempotent and skips tables
        # that may have been dropped or never existed in this environment.
        exists = bind.exec_driver_sql(
            "SELECT 1 FROM information_schema.columns "
            f"WHERE table_name = '{table}' AND column_name = '{column}'"
        ).fetchone()
        if not exists:
            continue
        op.execute(f'ALTER TABLE {table} ALTER COLUMN {column} TYPE TEXT')


def downgrade() -> None:
    # Intentionally a no-op: shrinking back to VARCHAR(500) would truncate
    # signed-URL data stored after this migration ran.
    pass
