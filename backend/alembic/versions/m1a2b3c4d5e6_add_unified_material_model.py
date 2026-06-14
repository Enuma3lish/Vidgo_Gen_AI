"""Add unified Material model

Revision ID: m1a2b3c4d5e6
Revises: d6f8f12ee01a
Create Date: 2025-01-01

Based on ARCHITECTURE_FINAL.md:
- Unified Material model for all 5 tools
- Material views for personalization
- Material topics configuration
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'm1a2b3c4d5e6'
down_revision = 'b2c3d4e5f6g7'  # After allow_null_source_image (latest)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types (with existence check)
    conn = op.get_bind()

    # Check and create tooltype enum
    result = conn.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'tooltype'"))
    if not result.fetchone():
        op.execute("CREATE TYPE tooltype AS ENUM ('background_removal', 'product_scene', 'try_on', 'room_redesign', 'short_video')")

    # Check and create materialsource enum
    result = conn.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'materialsource'"))
    if not result.fetchone():
        op.execute("CREATE TYPE materialsource AS ENUM ('seed', 'user', 'admin')")

    # Check and create materialstatus enum
    result = conn.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'materialstatus'"))
    if not result.fetchone():
        op.execute("CREATE TYPE materialstatus AS ENUM ('pending', 'approved', 'rejected', 'featured')")

    # Reference the enum types for column creation
    tool_type_enum = postgresql.ENUM('background_removal', 'product_scene', 'try_on', 'room_redesign', 'short_video', name='tooltype', create_type=False)
    material_source_enum = postgresql.ENUM('seed', 'user', 'admin', name='materialsource', create_type=False)
    material_status_enum = postgresql.ENUM('pending', 'approved', 'rejected', 'featured', name='materialstatus', create_type=False)

    # Create materials table
    op.create_table(
        'materials',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        # Classification
        sa.Column('tool_type', tool_type_enum, nullable=False, index=True),
        sa.Column('topic', sa.String(100), nullable=False, index=True),
        sa.Column('tags', postgresql.ARRAY(sa.String()), server_default='{}'),
        sa.Column('source', material_source_enum, nullable=False, server_default='seed'),
        sa.Column('source_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('status', material_status_enum, nullable=False, server_default='pending', index=True),
        # Input
        sa.Column('prompt', sa.Text, nullable=False),
        sa.Column('prompt_enhanced', sa.Text, nullable=True),
        sa.Column('input_image_url', sa.String(500), nullable=True),
        sa.Column('input_params', postgresql.JSONB, server_default='{}'),
        # Generation pipeline
        sa.Column('generation_steps', postgresql.JSONB, server_default='[]'),
        # Output
        sa.Column('result_image_url', sa.String(500), nullable=True),
        sa.Column('result_video_url', sa.String(500), nullable=True),
        sa.Column('result_thumbnail_url', sa.String(500), nullable=True),
        sa.Column('result_watermarked_url', sa.String(500), nullable=True),
        # Multi-language titles
        sa.Column('title_en', sa.String(255), nullable=True),
        sa.Column('title_zh', sa.String(255), nullable=True),
        sa.Column('title_ja', sa.String(255), nullable=True),
        # Multi-language descriptions
        sa.Column('description_en', sa.Text, nullable=True),
        sa.Column('description_zh', sa.Text, nullable=True),
        sa.Column('description_ja', sa.Text, nullable=True),
        # Statistics
        sa.Column('view_count', sa.Integer, server_default='0'),
        sa.Column('use_count', sa.Integer, server_default='0'),
        sa.Column('like_count', sa.Integer, server_default='0'),
        sa.Column('generation_cost_usd', sa.Float, server_default='0.0'),
        # Quality & Ranking
        sa.Column('quality_score', sa.Float, server_default='0.8'),
        sa.Column('sort_order', sa.Integer, server_default='0'),
        # Metadata
        sa.Column('duration_seconds', sa.Float, nullable=True),
        sa.Column('resolution', sa.String(20), nullable=True),
        # Flags
        sa.Column('is_featured', sa.Boolean, server_default='false'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Create indexes for materials
    op.create_index('idx_material_tool_topic', 'materials', ['tool_type', 'topic', 'is_active'])
    op.create_index('idx_material_featured', 'materials', ['is_featured', 'is_active'])
    op.create_index('idx_material_source', 'materials', ['source', 'source_user_id'])
    op.create_index('idx_material_tags', 'materials', ['tags'], postgresql_using='gin')

    # Create material_views table
    op.create_table(
        'material_views',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('material_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('materials.id'), nullable=False, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('session_id', sa.String(64), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('source_page', sa.String(50), nullable=True),
        sa.Column('viewed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create indexes for material_views
    op.create_index('idx_material_view_user', 'material_views', ['user_id', 'material_id'])
    op.create_index('idx_material_view_session', 'material_views', ['session_id', 'material_id'])

    # Create material_topics table
    op.create_table(
        'material_topics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tool_type', tool_type_enum, nullable=False, index=True),
        sa.Column('topic_id', sa.String(50), nullable=False),
        sa.Column('topic_name_en', sa.String(100), nullable=False),
        sa.Column('topic_name_zh', sa.String(100), nullable=True),
        sa.Column('topic_name_ja', sa.String(100), nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('target_count', sa.Integer, server_default='30'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('sort_order', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create index for material_topics
    op.create_index('idx_topic_tool', 'material_topics', ['tool_type', 'is_active'])


def downgrade() -> None:
    # Drop tables
    op.drop_table('material_views')
    op.drop_table('material_topics')
    op.drop_table('materials')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS materialstatus")
    op.execute("DROP TYPE IF EXISTS materialsource")
    op.execute("DROP TYPE IF EXISTS tooltype")
