from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, IDMixin, TimestampMixin


class Product(Base, IDMixin, TimestampMixin):
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_active_category", "is_active", "category"),
    )

    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), index=True)
    price: Mapped[float] = mapped_column(Float)
    discount_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    images: Mapped[list] = mapped_column(JSON, default=list)
    total_stock: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    review_count: Mapped[int] = mapped_column(Integer, default=0)


class ProductVariant(Base, IDMixin):
    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint("product_id", "sku", name="uq_variant_product_sku"),
        UniqueConstraint("product_id", "size", "color", name="uq_variant_product_size_color"),
    )

    product_id: Mapped[str] = mapped_column(String(24), ForeignKey("products.id", ondelete="CASCADE"), index=True)
    size: Mapped[str] = mapped_column(String(20))
    color: Mapped[str] = mapped_column(String(50))
    sku: Mapped[str] = mapped_column(String(100))
    stock: Mapped[int] = mapped_column(Integer, default=0)


class InventoryHistoryEntry(Base, IDMixin):
    """One row per log entry (replaces the Mongo design of one document per product with an
    unboundedly-growing `logs[]` array — also fixes the total lack of an index this collection
    had under Mongo despite being queried by product_id)."""
    __tablename__ = "inventory_history"

    product_id: Mapped[str] = mapped_column(String(24), ForeignKey("products.id", ondelete="CASCADE"), index=True)
    variant_sku: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    quantity_changed: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(100))
    admin_id: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
