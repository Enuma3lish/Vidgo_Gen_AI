"""Add demo usage tracking fields to users table

Revision ID: a1b2c3d4e5f6
Revises: 8ee2c1ad815f
Create Date: 2024-12-29

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '8ee2c1ad815f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add demo usage tracking columns to users table."""
    # Add demo usage tracking columns
    op.add_column('users', sa.Column('demo_usage_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('users', sa.Column('demo_usage_reset_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('demo_usage_limit', sa.Integer(), nullable=True, server_default='2'))


def downgrade() -> None:
    """Remove demo usage tracking columns from users table."""
    op.drop_column('users', 'demo_usage_limit')
    op.drop_column('users', 'demo_usage_reset_at')
    op.drop_column('users', 'demo_usage_count')
