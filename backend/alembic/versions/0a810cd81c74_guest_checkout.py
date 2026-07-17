"""guest checkout: nullable orders.user_id, add orders.guest_email

Revision ID: 0a810cd81c74
Revises: 3734422e0234
Create Date: 2026-07-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0a810cd81c74'
down_revision: Union[str, None] = '3734422e0234'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('orders', 'user_id', existing_type=sa.String(length=24), nullable=True)
    op.add_column('orders', sa.Column('guest_email', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_orders_guest_email'), 'orders', ['guest_email'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_orders_guest_email'), table_name='orders')
    op.drop_column('orders', 'guest_email')
    op.alter_column('orders', 'user_id', existing_type=sa.String(length=24), nullable=False)
