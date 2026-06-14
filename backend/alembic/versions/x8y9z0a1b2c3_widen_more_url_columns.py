"""Widen URL columns in user_generations, user_uploads, prompt_cache, demo_examples, demo_videos, tool_showcases

Revision ID: x8y9z0a1b2c3
Revises: w7x8y9z0a1b2
Create Date: 2026-05-07

The earlier migration w7x8y9z0a1b2 widened URL columns in materials,
generations, prompt_templates, demo_examples (legacy column names) and
demo_videos. However, the actual production tables `user_generations`,
`user_uploads`, `prompt_cache`, `tool_showcases`, and the current
`demo_examples`/`demo_videos` schemas still had VARCHAR(500) URL columns.

This caused signed-GCS provider URLs (>500 chars) to raise
asyncpg.exceptions.StringDataRightTruncationError on commit, observed on
/api/v1/tools/product-scene and /api/v1/tools/try-on at db.commit().

This migration converts the remaining URL-bearing columns to TEXT.
"""
from alembic import op


revision = 'x8y9z0a1b2c3'
down_revision = 'w7x8y9z0a1b2'
branch_labels = None
depends_on = None


URL_COLUMNS = [
    ('user_generations', 'input_image_url'),
    ('user_generations', 'input_video_url'),
    ('user_generations', 'input_text'),
    ('user_generations', 'result_image_url'),
    ('user_generations', 'result_video_url'),
    ('user_uploads', 'file_url'),
    ('user_uploads', 'result_url'),
    ('user_uploads', 'result_video_url'),
    ('prompt_cache', 'image_url'),
    ('prompt_cache', 'video_url'),
    ('prompt_cache', 'video_url_watermarked'),
    ('demo_examples', 'image_url'),
    ('demo_examples', 'video_url'),
    ('demo_examples', 'video_url_watermarked'),
    ('demo_examples', 'thumbnail_url'),
    ('demo_videos', 'image_url'),
    ('demo_videos', 'video_url'),
    ('demo_videos', 'video_url_watermarked'),
    ('demo_videos', 'thumbnail_url'),
    ('tool_showcases', 'source_image_url'),
    ('tool_showcases', 'source_thumbnail_url'),
    ('tool_showcases', 'result_image_url'),
    ('tool_showcases', 'result_video_url'),
    ('tool_showcases', 'result_thumbnail_url'),
]


def upgrade() -> None:
    bind = op.get_bind()
    for table, column in URL_COLUMNS:
        exists = bind.exec_driver_sql(
            "SELECT 1 FROM information_schema.columns "
            f"WHERE table_name = '{table}' AND column_name = '{column}'"
        ).fetchone()
        if not exists:
            continue
        op.execute(f'ALTER TABLE {table} ALTER COLUMN {column} TYPE TEXT')


def downgrade() -> None:
    # No-op: shrinking back to VARCHAR(500) would truncate data stored after migration.
    pass
