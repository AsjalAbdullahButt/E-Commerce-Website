from typing import Optional

from sqlalchemy import JSON, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import ID_TYPE, Base, IDMixin, TimestampMixin


class Payment(Base, IDMixin, TimestampMixin):
    """One row per payment attempt on an order (not per order) — a failed JazzCash attempt
    followed by a customer retry produces a second row, so every attempt stays auditable.
    Order.payment_status is a denormalized snapshot of the latest attempt's outcome, kept in
    sync by services/payment.py, so order lists/admin dashboard never need to join here."""
    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_order_status", "order_id", "status"),
    )

    order_id: Mapped[str] = mapped_column(ID_TYPE, ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    gateway: Mapped[str] = mapped_column(String(20))  # stripe | jazzcash | easypaisa
    status: Mapped[str] = mapped_column(String(20), default="initiated", index=True)

    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="PKR")

    # The gateway's own transaction identifier, once known — not unique across gateways (each
    # gateway has its own ID namespace), so no unique constraint here. gateway_event_id below is
    # the one that guards against double-processing.
    gateway_transaction_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Idempotency guard for webhook redelivery: gateways (Stripe especially) redeliver
    # aggressively. A previously-recorded event_id is a no-op, not an error.
    gateway_event_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, unique=True, index=True)

    # Idempotency guard for retried POST /payments/{order_id}/initiate calls — lets a repeat
    # request return the existing attempt instead of calling the gateway (and, for Stripe,
    # minting a second PaymentIntent) a second time.
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, unique=True, index=True)

    # Holds whatever we most recently know about this attempt: the gateway's initiate response
    # while status is initiated/processing (so an idempotent replay can re-serve the same
    # redirect/client_secret), then overwritten with the webhook payload once it resolves —
    # useful for audit either way.
    raw_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
