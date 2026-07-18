from typing import Optional

from sqlalchemy import Boolean, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IDMixin, TimestampMixin


class Address(Base, IDMixin, TimestampMixin):
    """A customer's saved shipping address — multiple per user, at most one flagged as default
    (enforced in services/address.py, not a DB constraint, same convention as
    db/return_request.py's "one pending request" rule). Orders still flatten the chosen address
    onto themselves at checkout time (db/order.py) — a saved Address is only ever a template to
    prefill from, never referenced live by a placed order, so editing/deleting one never rewrites
    order history. user_id is a plain indexed column, not a DB-level foreign key — matches every
    other user_id column in this schema (db/order.py, db/review.py, db/wishlist.py)."""
    __tablename__ = "addresses"
    __table_args__ = (
        Index("ix_addresses_user_default", "user_id", "is_default"),
    )

    user_id: Mapped[str] = mapped_column(String(24), index=True)
    label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g. "Home", "Work"
    full_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(String(500))
    city: Mapped[str] = mapped_column(String(100))
    postal_code: Mapped[str] = mapped_column(String(20))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
