"""add cancellation and work retention fields to users

Revision ID: t2u3v4w5x6y7
Revises: 1bb965787d97
Create Date: 2026-03-13 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 't2u3v4w5x6y7'
down_revision: Union[str, None] = '1bb965787d97'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add cancellation tracking fields to users table
    op.add_column('users', sa.Column(
        'subscription_cancelled_at',
        sa.DateTime(timezone=True),
        nullable=True
    ))
    op.add_column('users', sa.Column(
        'work_retention_until',
        sa.DateTime(timezone=True),
        nullable=True,
        comment='7 days after cancellation - user can download work until this date'
    ))


def downgrade() -> None:
    op.drop_column('users', 'work_retention_until')
    op.drop_column('users', 'subscription_cancelled_at')
