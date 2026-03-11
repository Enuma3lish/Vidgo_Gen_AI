"""Add expires_at and media_expired to user_generations"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2a1e7d2ed4bb'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('user_generations', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True, comment='Media files expire 14 days after creation; record kept permanently'))
    op.add_column('user_generations', sa.Column('media_expired', sa.Boolean(), server_default=sa.text('false'), nullable=False, comment='True when media URLs have been cleared after expiry'))
    op.create_index(op.f('ix_user_generations_expires_at'), 'user_generations', ['expires_at'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_user_generations_expires_at'), table_name='user_generations')
    op.drop_column('user_generations', 'media_expired')
    op.drop_column('user_generations', 'expires_at')
