"""add social accounts and posts tables

Revision ID: u3v4w5x6y7z8
Revises: t2u3v4w5x6y7
Create Date: 2026-03-17 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'u3v4w5x6y7z8'
down_revision: Union[str, None] = 't2u3v4w5x6y7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create social_accounts table
    op.create_table(
        'social_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('platform', sa.String(32), nullable=False, index=True),
        sa.Column('platform_user_id', sa.String(256), nullable=True),
        sa.Column('platform_username', sa.String(256), nullable=True),
        sa.Column('platform_avatar', sa.String(512), nullable=True),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('page_id', sa.String(256), nullable=True),
        sa.Column('open_id', sa.String(256), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'platform', name='uq_social_account_user_platform'),
    )
    op.create_index('ix_social_accounts_id', 'social_accounts', ['id'])

    # Create social_posts table
    op.create_table(
        'social_posts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('social_account_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('generation_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('platform', sa.String(32), nullable=False, index=True),
        sa.Column('platform_post_id', sa.String(256), nullable=True),
        sa.Column('post_url', sa.String(1024), nullable=True),
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('media_type', sa.String(32), nullable=True),
        sa.Column('status', sa.String(32), default='published', nullable=False),
        sa.Column('likes_count', sa.Integer(), default=0),
        sa.Column('comments_count', sa.Integer(), default=0),
        sa.Column('shares_count', sa.Integer(), default=0),
        sa.Column('views_count', sa.Integer(), default=0),
        sa.Column('analytics_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['social_account_id'], ['social_accounts.id'], ondelete='SET NULL'),
    )
    op.create_index('idx_social_post_user_platform', 'social_posts', ['user_id', 'platform'])
    op.create_index('idx_social_post_published', 'social_posts', ['published_at'])


def downgrade() -> None:
    op.drop_table('social_posts')
    op.drop_table('social_accounts')