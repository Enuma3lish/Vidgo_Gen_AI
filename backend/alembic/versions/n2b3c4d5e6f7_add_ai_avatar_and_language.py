"""Add AI Avatar tool type and language field to materials

Revision ID: n2b3c4d5e6f7
Revises: m1a2b3c4d5e6
Create Date: 2025-01-02

Changes:
- Add 'ai_avatar' to tooltype enum
- Add 'language' column to materials table for language-specific content
- Add index for language-based queries
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'n2b3c4d5e6f7'
down_revision = 'm1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add 'ai_avatar' to tooltype enum
    # PostgreSQL requires special handling for adding enum values
    op.execute("ALTER TYPE tooltype ADD VALUE IF NOT EXISTS 'ai_avatar'")

    # Add language column to materials table
    op.add_column('materials', sa.Column('language', sa.String(10), server_default='en', nullable=True))

    # Create index for language-based queries
    op.create_index('idx_material_language', 'materials', ['language', 'tool_type', 'is_active'])

    # Update existing materials to have default language
    op.execute("UPDATE materials SET language = 'en' WHERE language IS NULL")


def downgrade() -> None:
    # Drop the language index
    op.drop_index('idx_material_language', 'materials')

    # Drop the language column
    op.drop_column('materials', 'language')

    # Note: Cannot easily remove enum value in PostgreSQL
    # The 'ai_avatar' value will remain in the enum
