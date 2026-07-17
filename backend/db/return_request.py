from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import ID_TYPE, Base, IDMixin, TimestampMixin


class ReturnRequest(Base, IDMixin, TimestampMixin):
    """A customer-initiated return/refund request on a delivered order — one row per request.
    Only one request may be `pending` per order at a time (enforced in
    services/order_user.py, not a DB constraint, matching the codebase's existing convention of
    validating order-adjacent business rules in the service/route layer rather than the schema)."""
    __tablename__ = "return_requests"
    __table_args__ = (
        Index("ix_return_requests_order_status", "order_id", "status"),
    )

    order_id: Mapped[str] = mapped_column(ID_TYPE, ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending | approved | rejected

    refund_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    admin_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
