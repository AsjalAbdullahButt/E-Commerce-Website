from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import ID_TYPE, Base, IDMixin, TimestampMixin


class Order(Base, IDMixin, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_status_created", "status", "created_at"),
        Index("ix_orders_rider_status", "rider_id", "status"),
    )

    # Nullable for guest checkout — a guest order has user_id=None and guest_email set instead.
    # Never both unset: routes/orders.py::place_order requires one or the other.
    user_id: Mapped[Optional[str]] = mapped_column(String(24), nullable=True, index=True)
    guest_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    rider_id: Mapped[Optional[str]] = mapped_column(String(24), nullable=True, index=True)

    subtotal: Mapped[float] = mapped_column(Float)
    discount: Mapped[float] = mapped_column(Float, default=0.0)
    tax: Mapped[float] = mapped_column(Float, default=0.0)
    delivery_fee: Mapped[float] = mapped_column(Float, default=0.0)
    total: Mapped[float] = mapped_column(Float)

    payment_method: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    payment_reference: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # Denormalized snapshot of the latest Payment row's outcome (db/payment.py) — kept in sync by
    # services/payment.py so order lists/admin dashboard never need to join to know payment state.
    # "not_required" for COD (nothing to process), "unpaid" until an online gateway resolves.
    payment_status: Mapped[str] = mapped_column(String(20), default="not_required", index=True)
    # Client-supplied Idempotency-Key header (routes/orders.py::place_order) — a retried checkout
    # submission with the same key returns the already-created order instead of a duplicate one.
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, unique=True, index=True)
    promo_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Shipping address, flattened onto the order — always 1:1, never queried independently, no
    # separate addresses concept exists anywhere in the app.
    full_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(String(500))
    city: Mapped[str] = mapped_column(String(100))
    postal_code: Mapped[str] = mapped_column(String(20))

    # Set by routes/rider.py::complete_delivery when the rider attaches a photo — optional, since
    # requiring one is enforced client-side only (see frontend/rider/assigned-orders.html), not here.
    proof_of_delivery_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


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
    timestamp: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class OrderNote(Base, IDMixin):
    __tablename__ = "order_notes"

    order_id: Mapped[str] = mapped_column(ID_TYPE, ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    added_by: Mapped[str] = mapped_column(String(24))
    timestamp: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
