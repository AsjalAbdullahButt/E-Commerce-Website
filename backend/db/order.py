from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import ID_TYPE, Base, IDMixin, TimestampMixin


class Order(Base, IDMixin, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_status_created", "status", "created_at"),
        Index("ix_orders_rider_status", "rider_id", "status"),
    )

    user_id: Mapped[str] = mapped_column(String(24), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    rider_id: Mapped[Optional[str]] = mapped_column(String(24), nullable=True, index=True)

    subtotal: Mapped[float] = mapped_column(Float)
    discount: Mapped[float] = mapped_column(Float, default=0.0)
    tax: Mapped[float] = mapped_column(Float, default=0.0)
    delivery_fee: Mapped[float] = mapped_column(Float, default=0.0)
    total: Mapped[float] = mapped_column(Float)

    payment_method: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    payment_reference: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    promo_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Shipping address, flattened onto the order — always 1:1, never queried independently, no
    # separate addresses concept exists anywhere in the app.
    full_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(String(500))
    city: Mapped[str] = mapped_column(String(100))
    postal_code: Mapped[str] = mapped_column(String(20))


class OrderItem(Base, IDMixin):
    __tablename__ = "order_items"

    order_id: Mapped[str] = mapped_column(ID_TYPE, ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(String(24))
    name: Mapped[str] = mapped_column(String(200))
    price: Mapped[float] = mapped_column(Float)
    quantity: Mapped[int] = mapped_column(Integer)
    size: Mapped[str] = mapped_column(String(20))
    color: Mapped[str] = mapped_column(String(50))
    image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class OrderStatusHistory(Base, IDMixin):
    __tablename__ = "order_status_history"

    order_id: Mapped[str] = mapped_column(ID_TYPE, ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class OrderNote(Base, IDMixin):
    __tablename__ = "order_notes"

    order_id: Mapped[str] = mapped_column(ID_TYPE, ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    added_by: Mapped[str] = mapped_column(String(24))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
