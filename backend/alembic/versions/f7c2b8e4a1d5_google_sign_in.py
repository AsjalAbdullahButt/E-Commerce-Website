"""Google Sign-In: nullable local password, provider/sub/verification/avatar columns

Revision ID: f7c2b8e4a1d5
Revises: d4e8f1a9c6b2
Create Date: 2026-07-20 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f7c2b8e4a1d5'
down_revision: Union[str, None] = 'd4e8f1a9c6b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('users', 'password', existing_type=sa.String(length=255), nullable=True)
    op.add_column('users', sa.Column('auth_provider', sa.String(length=20), nullable=False, server_default='local'))
    op.add_column('users', sa.Column('google_sub', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('avatar_url', sa.String(length=500), nullable=True))
    op.create_unique_constraint('uq_users_google_sub', 'users', ['google_sub'])


def downgrade() -> None:
    op.drop_constraint('uq_users_google_sub', 'users', type_='unique')
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'email_verified')
    op.drop_column('users', 'google_sub')
    op.drop_column('users', 'auth_provider')
    op.alter_column('users', 'password', existing_type=sa.String(length=255), nullable=False)
