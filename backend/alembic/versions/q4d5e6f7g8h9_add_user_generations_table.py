"""Add user_generations table

Revision ID: q4d5e6f7g8h9
Revises: p3c4d5e6f7g8
Create Date: 2026-01-25

Stores subscribed users' on-demand generated content:
- No watermark on results
- Download enabled
- Personal gallery for users
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = 'q4d5e6f7g8h9'
down_revision = 'p3c4d5e6f7g8'
branch_labels = None
depends_on = None


def upgrade():
    # Create tool_type enum if not exists (should already exist from material)
    tool_type = postgresql.ENUM(
        'background_removal', 'product_scene', 'try_on', 
        'room_redesign', 'short_video', 'ai_avatar', 'pattern_generate',
        name='tooltype',
        create_type=False
    )
    
    op.create_table(
        'user_generations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        
        # Tool Classification
        sa.Column('tool_type', tool_type, nullable=False, index=True),
        
        # Input Data
        sa.Column('input_image_url', sa.String(500), nullable=True),
        sa.Column('input_video_url', sa.String(500), nullable=True),
        sa.Column('input_params', postgresql.JSONB, server_default='{}'),
        sa.Column('prompt', sa.Text, nullable=True),
        
        # Output Data (NO watermark for subscribers)
        sa.Column('result_image_url', sa.String(500), nullable=True),
        sa.Column('result_video_url', sa.String(500), nullable=True),
        sa.Column('result_thumbnail_url', sa.String(500), nullable=True),
        
        # Generation Details
        sa.Column('generation_steps', postgresql.JSONB, server_default='[]'),
        sa.Column('credits_used', sa.Integer, default=0),
        sa.Column('generation_cost_usd', sa.Float, default=0.0),
        
        # Status
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('error_message', sa.Text, nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        
        # Soft delete
        sa.Column('is_deleted', sa.Boolean, default=False),
    )
    
    # Create indexes
    op.create_index('idx_user_gen_user_tool', 'user_generations', ['user_id', 'tool_type'])
    op.create_index('idx_user_gen_created', 'user_generations', ['created_at'])


def downgrade():
    op.drop_index('idx_user_gen_created', table_name='user_generations')
    op.drop_index('idx_user_gen_user_tool', table_name='user_generations')
    op.drop_table('user_generations')
