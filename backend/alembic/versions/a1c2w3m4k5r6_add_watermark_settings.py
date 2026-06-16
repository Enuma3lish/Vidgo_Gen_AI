"""Admin-configurable demo watermark settings on site_settings

Revision ID: a1c2w3m4k5r6
Revises: z1a2b3c4d5e6
Create Date: 2026-06-15

Adds watermark configuration to the singleton `site_settings` row so admins can
upload a logo PNG + tune text/position/opacity from the admin panel. Free /
visitor users see watermarked example outputs; subscribers get the clean
result. Idempotent ADD COLUMN IF NOT EXISTS so it can be replayed safely (the
prod alembic history has multiple heads and is applied manually).
"""
from alembic import op
import sqlalchemy as sa


revision = 'a1c2w3m4k5r6'
# Chain off the real single head (n3o4p5q6r7s8, the v2.1/i18n merge) so
# `alembic upgrade head` stays unambiguous. Originally pointed at z1a2b3c4d5e6,
# which is deep in the tree (3 children) and created a 2nd head → startup crash.
down_revision = 'n3o4p5q6r7s8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {
        row[0] for row in bind.exec_driver_sql(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'site_settings'"
        ).fetchall()
    }
    if 'watermark_enabled' not in existing:
        op.add_column('site_settings', sa.Column(
            'watermark_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
    if 'watermark_image_url' not in existing:
        op.add_column('site_settings', sa.Column('watermark_image_url', sa.Text(), nullable=True))
    if 'watermark_text' not in existing:
        op.add_column('site_settings', sa.Column('watermark_text', sa.String(length=120), nullable=True))
    if 'watermark_position' not in existing:
        op.add_column('site_settings', sa.Column(
            'watermark_position', sa.String(length=20), nullable=True, server_default='bottom_right'))
    if 'watermark_opacity' not in existing:
        op.add_column('site_settings', sa.Column(
            'watermark_opacity', sa.Integer(), nullable=True, server_default='70'))


def downgrade() -> None:
    bind = op.get_bind()
    existing = {
        row[0] for row in bind.exec_driver_sql(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'site_settings'"
        ).fetchall()
    }
    for col in ('watermark_opacity', 'watermark_position', 'watermark_text',
                'watermark_image_url', 'watermark_enabled'):
        if col in existing:
            op.drop_column('site_settings', col)
