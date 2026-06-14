"""Add platform and role audience-tag columns to materials

Revision ID: y9z0a1b2c3d4
Revises: x8y9z0a1b2c3
Create Date: 2026-05-08

Adds two optional audience-tag columns to the `materials` table so the public
library / inspiration grid can filter pre-generated content by the platform
the seed targets (e.g. 'instagram', 'tiktok', 'shopify') and the user role
it was authored for (e.g. 'creator', 'seller', 'designer'). Both columns are
nullable so legacy rows continue to work; queries that omit the filter still
match every row.

Also adds a composite index on (platform, role, tool_type, is_active) to keep
filtered library queries cheap.
"""
from alembic import op
import sqlalchemy as sa


revision = 'y9z0a1b2c3d4'
down_revision = 'x8y9z0a1b2c3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'materials',
        sa.Column('platform', sa.String(length=40), nullable=True),
    )
    op.add_column(
        'materials',
        sa.Column('role', sa.String(length=40), nullable=True),
    )
    op.create_index(
        'ix_materials_platform',
        'materials',
        ['platform'],
        unique=False,
    )
    op.create_index(
        'ix_materials_role',
        'materials',
        ['role'],
        unique=False,
    )
    op.create_index(
        'idx_material_audience',
        'materials',
        ['platform', 'role', 'tool_type', 'is_active'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('idx_material_audience', table_name='materials')
    op.drop_index('ix_materials_role', table_name='materials')
    op.drop_index('ix_materials_platform', table_name='materials')
    op.drop_column('materials', 'role')
    op.drop_column('materials', 'platform')
