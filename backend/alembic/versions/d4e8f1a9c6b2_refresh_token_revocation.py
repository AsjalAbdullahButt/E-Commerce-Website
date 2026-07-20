"""refresh token revocation store + reuse-detection kill switch

Revision ID: d4e8f1a9c6b2
Revises: a1c7e4f92b3d
Create Date: 2026-07-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4e8f1a9c6b2'
down_revision: Union[str, None] = 'a1c7e4f92b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'revoked_tokens',
        sa.Column('jti', sa.String(length=24), nullable=False),
        sa.Column('user_id', sa.String(length=24), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('jti'),
    )
    op.create_index('ix_revoked_tokens_expires_at', 'revoked_tokens', ['expires_at'])
    op.create_index('ix_revoked_tokens_user_id', 'revoked_tokens', ['user_id'])

    op.add_column('users', sa.Column('tokens_invalidated_at', sa.DateTime(), nullable=True))
    op.add_column('admin_users', sa.Column('tokens_invalidated_at', sa.DateTime(), nullable=True))
    op.add_column('riders', sa.Column('tokens_invalidated_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('riders', 'tokens_invalidated_at')
    op.drop_column('admin_users', 'tokens_invalidated_at')
    op.drop_column('users', 'tokens_invalidated_at')
    op.drop_index('ix_revoked_tokens_user_id', table_name='revoked_tokens')
    op.drop_index('ix_revoked_tokens_expires_at', table_name='revoked_tokens')
    op.drop_table('revoked_tokens')
