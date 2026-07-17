"""add payments table and order payment_status/idempotency_key

Revision ID: 3734422e0234
Revises: fd959b887b9a
Create Date: 2026-07-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '3734422e0234'
down_revision: Union[str, None] = 'fd959b887b9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('payment_status', sa.String(length=20), nullable=False, server_default='not_required'))
    op.add_column('orders', sa.Column('idempotency_key', sa.String(length=200), nullable=True))
    op.alter_column('orders', 'payment_status', server_default=None)
    op.create_index(op.f('ix_orders_payment_status'), 'orders', ['payment_status'], unique=False)
    op.create_index(op.f('ix_orders_idempotency_key'), 'orders', ['idempotency_key'], unique=True)

    op.create_table('payments',
    sa.Column('order_id', mysql.CHAR(charset='ascii', collation='ascii_bin', length=24), nullable=False),
    sa.Column('gateway', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.Column('currency', sa.String(length=10), nullable=False),
    sa.Column('gateway_transaction_id', sa.String(length=200), nullable=True),
    sa.Column('gateway_event_id', sa.String(length=200), nullable=True),
    sa.Column('idempotency_key', sa.String(length=200), nullable=True),
    sa.Column('raw_response', sa.JSON(), nullable=True),
    sa.Column('failure_reason', sa.String(length=500), nullable=True),
    sa.Column('id', mysql.CHAR(charset='ascii', collation='ascii_bin', length=24), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('gateway_event_id', name='uq_payments_gateway_event_id'),
    sa.UniqueConstraint('idempotency_key', name='uq_payments_idempotency_key'),
    )
    op.create_index(op.f('ix_payments_order_id'), 'payments', ['order_id'], unique=False)
    op.create_index(op.f('ix_payments_status'), 'payments', ['status'], unique=False)
    op.create_index(op.f('ix_payments_gateway_event_id'), 'payments', ['gateway_event_id'], unique=False)
    op.create_index(op.f('ix_payments_idempotency_key'), 'payments', ['idempotency_key'], unique=False)
    op.create_index('ix_payments_order_status', 'payments', ['order_id', 'status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_payments_order_status', table_name='payments')
    op.drop_index(op.f('ix_payments_idempotency_key'), table_name='payments')
    op.drop_index(op.f('ix_payments_gateway_event_id'), table_name='payments')
    op.drop_index(op.f('ix_payments_status'), table_name='payments')
    op.drop_index(op.f('ix_payments_order_id'), table_name='payments')
    op.drop_table('payments')
    op.drop_index(op.f('ix_orders_idempotency_key'), table_name='orders')
    op.drop_index(op.f('ix_orders_payment_status'), table_name='orders')
    op.drop_column('orders', 'idempotency_key')
    op.drop_column('orders', 'payment_status')
