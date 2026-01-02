"""Allow NULL source_image_url for TEXT-TO-IMAGE tools

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2025-12-30

For TEXT-TO-IMAGE tools like pattern_generate, there is no source image.
The user provides only a text prompt, and the AI generates the result.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6g7'
down_revision = 'a1b2c3d4e5f6'  # After demo_usage_tracking
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Allow NULL for source_image_url to support TEXT-TO-IMAGE tools
    op.alter_column(
        'tool_showcases',
        'source_image_url',
        existing_type=sa.String(500),
        nullable=True
    )


def downgrade() -> None:
    # Revert to NOT NULL (will fail if any rows have NULL)
    op.alter_column(
        'tool_showcases',
        'source_image_url',
        existing_type=sa.String(500),
        nullable=False
    )
