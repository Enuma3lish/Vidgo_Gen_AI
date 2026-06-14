"""add style_templates table

Revision ID: s1t2y3l4e5t6
Revises: 05a5bdfb49cf
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = 's1t2y3l4e5t6'
down_revision = '05a5bdfb49cf'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'style_templates',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tool_type', sa.String(50), nullable=False, index=True),
        sa.Column('category', sa.String(100), nullable=False, index=True),
        sa.Column('name_en', sa.String(200), nullable=False),
        sa.Column('name_zh', sa.String(200), nullable=False),
        sa.Column('name_ja', sa.String(200), nullable=True),
        sa.Column('name_ko', sa.String(200), nullable=True),
        sa.Column('name_es', sa.String(200), nullable=True),
        sa.Column('preview_image_url', sa.String(1000), nullable=True),
        sa.Column('prompt_en', sa.Text(), nullable=False),
        sa.Column('prompt_metadata', JSONB, nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_featured', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('style_templates')
