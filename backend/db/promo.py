from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IDMixin, TimestampMixin


class Promo(Base, IDMixin, TimestampMixin):
    """Backs both the customer-facing /promos endpoints and the admin /admin/discounts
    endpoints — two independent writers on the same table (see NOTES_schema_audit.md), which
    already agree on field names today. `description`/`created_by` are only ever set by the
    /admin/discounts path, nullable here since /promos never sets them."""
    __tablename__ = "promos"

    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    discount_type: Mapped[str] = mapped_column(String(20))  # percentage | fixed
    discount_value: Mapped[float] = mapped_column(Float)
    min_order: Mapped[float] = mapped_column(Float, default=0.0)
    max_uses: Mapped[int] = mapped_column(Integer, default=100)
    uses: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
