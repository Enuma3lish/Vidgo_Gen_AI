"""add referral system and user uploads table

Revision ID: r1s2t3u4v5w6
Revises: p3c4d5e6f7g8
Create Date: 2026-02-21 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'r1s2t3u4v5w6'
down_revision: Union[str, None] = '99d728708134'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add referral fields to users table
    op.add_column('users', sa.Column('referral_code', sa.String(16), nullable=True))
    op.add_column('users', sa.Column('referred_by_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('users', sa.Column('referral_count', sa.Integer(), nullable=True, server_default='0'))

    op.create_index('ix_users_referral_code', 'users', ['referral_code'], unique=True)
    op.create_foreign_key(
        'fk_users_referred_by_id',
        'users', 'users',
        ['referred_by_id'], ['id'],
        ondelete='SET NULL'
    )

    # Create uploadstatus enum (idempotent: ignore if already exists)
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE uploadstatus AS ENUM ('pending', 'processing', 'completed', 'failed');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
    """)
    upload_status_enum = postgresql.ENUM(
        'pending', 'processing', 'completed', 'failed',
        name='uploadstatus',
        create_type=False,
    )

    # Create user_uploads table
    op.create_table(
        'user_uploads',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('tool_type', sa.String(50), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=True),
        sa.Column('file_url', sa.String(500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('content_type', sa.String(100), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=True),
        sa.Column('selected_model', sa.String(100), nullable=True),
        sa.Column('extra_params', sa.Text(), nullable=True),
        sa.Column('status', upload_status_enum, nullable=False, server_default='pending'),
        sa.Column('task_id', sa.String(200), nullable=True),
        sa.Column('result_url', sa.String(500), nullable=True),
        sa.Column('result_video_url', sa.String(500), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('credits_used', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_user_uploads_user_id', 'user_uploads', ['user_id'])
    op.create_index('ix_user_uploads_tool_type', 'user_uploads', ['tool_type'])
    op.create_index('ix_user_uploads_status', 'user_uploads', ['status'])


def downgrade() -> None:
    op.drop_table('user_uploads')
    op.execute("DROP TYPE IF EXISTS uploadstatus")

    op.drop_constraint('fk_users_referred_by_id', 'users', type_='foreignkey')
    op.drop_index('ix_users_referral_code', table_name='users')
    op.drop_column('users', 'referral_count')
    op.drop_column('users', 'referred_by_id')
    op.drop_column('users', 'referral_code')
