"""add proof_of_delivery_url to orders

Revision ID: a1c7e4f92b3d
Revises: 063d2450b2eb
Create Date: 2026-07-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1c7e4f92b3d'
down_revision: Union[str, None] = '063d2450b2eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('proof_of_delivery_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'proof_of_delivery_url')
