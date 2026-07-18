"""add addresses table

Revision ID: 063d2450b2eb
Revises: 78b920f61b7a
Create Date: 2026-07-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '063d2450b2eb'
down_revision: Union[str, None] = '78b920f61b7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('addresses',
    sa.Column('user_id', sa.String(length=24), nullable=False),
    sa.Column('label', sa.String(length=50), nullable=True),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=False),
    sa.Column('address', sa.String(length=500), nullable=False),
    sa.Column('city', sa.String(length=100), nullable=False),
    sa.Column('postal_code', sa.String(length=20), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('id', mysql.CHAR(charset='ascii', collation='ascii_bin', length=24), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_addresses_user_id'), 'addresses', ['user_id'], unique=False)
    op.create_index(op.f('ix_addresses_is_default'), 'addresses', ['is_default'], unique=False)
    op.create_index('ix_addresses_user_default', 'addresses', ['user_id', 'is_default'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_addresses_user_default', table_name='addresses')
    op.drop_index(op.f('ix_addresses_is_default'), table_name='addresses')
    op.drop_index(op.f('ix_addresses_user_id'), table_name='addresses')
    op.drop_table('addresses')
