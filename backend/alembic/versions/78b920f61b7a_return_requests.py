"""add return_requests table

Revision ID: 78b920f61b7a
Revises: 0a810cd81c74
Create Date: 2026-07-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '78b920f61b7a'
down_revision: Union[str, None] = '0a810cd81c74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('return_requests',
    sa.Column('order_id', mysql.CHAR(charset='ascii', collation='ascii_bin', length=24), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('refund_amount', sa.Float(), nullable=True),
    sa.Column('admin_note', sa.Text(), nullable=True),
    sa.Column('resolved_by', sa.String(length=24), nullable=True),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.Column('id', mysql.CHAR(charset='ascii', collation='ascii_bin', length=24), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_return_requests_order_id'), 'return_requests', ['order_id'], unique=False)
    op.create_index(op.f('ix_return_requests_status'), 'return_requests', ['status'], unique=False)
    op.create_index('ix_return_requests_order_status', 'return_requests', ['order_id', 'status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_return_requests_order_status', table_name='return_requests')
    op.drop_index(op.f('ix_return_requests_status'), table_name='return_requests')
    op.drop_index(op.f('ix_return_requests_order_id'), table_name='return_requests')
    op.drop_table('return_requests')
