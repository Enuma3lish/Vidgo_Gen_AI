"""Add pattern_generate tool type and MATERIAL_TOPICS configuration

Revision ID: p3c4d5e6f7g8
Revises: bae2b07d4b94
Create Date: 2026-01-18

Changes:
- Add 'pattern_generate' to tooltype enum for pattern design functionality
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'p3c4d5e6f7g8'
down_revision = 'bae2b07d4b94'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add 'pattern_generate' to tooltype enum
    # PostgreSQL requires special handling for adding enum values
    op.execute("ALTER TYPE tooltype ADD VALUE IF NOT EXISTS 'pattern_generate'")


def downgrade() -> None:
    # Note: Cannot easily remove enum value in PostgreSQL
    # The 'pattern_generate' value will remain in the enum
    pass
