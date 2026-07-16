from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IDMixin


class WishlistItem(Base, IDMixin):
    __tablename__ = "wishlist"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_wishlist_user_product"),
    )

    user_id: Mapped[str] = mapped_column(String(24), index=True)
    product_id: Mapped[str] = mapped_column(String(24), index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
