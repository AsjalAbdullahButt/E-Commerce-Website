from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.product import InventoryHistoryEntry, Product, ProductVariant
from utils.logger import get_logger

logger = get_logger(__name__)


def _variant_to_dict(v: ProductVariant) -> dict:
    return {"size": v.size, "color": v.color, "sku": v.sku, "stock": v.stock}


async def _product_to_dict(db: AsyncSession, product: Product) -> dict:
    result = await db.execute(select(ProductVariant).where(ProductVariant.product_id == product.id))
    variants = [_variant_to_dict(v) for v in result.scalars().all()]
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "category": product.category,
        "price": product.price,
        "discount_percentage": product.discount_percentage,
        "discount_price": product.price * (1 - product.discount_percentage / 100),
        "variants": variants,
        "tags": product.tags or [],
        "images": product.images or [],
        "total_stock": product.total_stock,
        "is_active": product.is_active,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
        "created_by": product.created_by,
        "rating": product.rating,
        "review_count": product.review_count,
    }


class ProductService:
    """Product management service"""

    @staticmethod
    async def create_product(
        db: AsyncSession,
        name: str,
        description: str,
        category: str,
        price: float,
        discount_percentage: float,
        variants: List[dict],
        tags: List[str],
        images: List[str],
        admin_id: str,
    ) -> str:
        """Create new product"""
        total_stock = sum(v.get("stock", 0) for v in variants)
        product = Product(
            name=name,
            description=description,
            category=category,
            price=price,
            discount_percentage=discount_percentage,
            tags=tags,
            images=images,
            total_stock=total_stock,
            is_active=True,
            created_by=admin_id,
        )
        db.add(product)
        await db.flush()  # populate product.id before referencing it in variants

        for v in variants:
            db.add(ProductVariant(
                product_id=product.id,
                size=v["size"],
                color=v["color"],
                sku=v["sku"],
                stock=v.get("stock", 0),
            ))

        logger.info(f"Product created: {name} ({product.id}) by admin {admin_id}")
        return product.id

    @staticmethod
    async def get_product(db: AsyncSession, product_id: str) -> dict:
        """Get product by ID"""
        product = await db.get(Product, product_id)

        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )

        return await _product_to_dict(db, product)

    @staticmethod
    async def update_product(
        db: AsyncSession,
        product_id: str,
        updates: dict,
        admin_id: str,
    ) -> dict:
        """Update product"""
        current = await ProductService.get_product(db, product_id)
        product = await db.get(Product, product_id)

        variants = updates.pop("variants", None)
        if variants is not None:
            updates["total_stock"] = sum(v.get("stock", 0) for v in variants)
            # Replace the whole variant set (matches the old $set: {variants: [...]} semantics).
            await db.execute(delete(ProductVariant).where(ProductVariant.product_id == product_id))
            for v in variants:
                db.add(ProductVariant(
                    product_id=product_id,
                    size=v["size"],
                    color=v["color"],
                    sku=v["sku"],
                    stock=v.get("stock", 0),
                ))

        for key, value in updates.items():
            setattr(product, key, value)
        product.updated_at = datetime.utcnow()
        await db.flush()

        # Log audit
        from services.admin_auth import AdminAuditService
        await AdminAuditService.log_action(
            db,
            admin_id=admin_id,
            admin_name="System",
            action="update_product",
            entity_type="product",
            entity_id=product_id,
            changes={k: {"old": current.get(k), "new": v} for k, v in {**updates, "variants": variants}.items() if v is not None},
            ip_address="0.0.0.0"
        )

        logger.info(f"Product updated: {product_id} by admin {admin_id}")
        return await ProductService.get_product(db, product_id)

    @staticmethod
    async def delete_product(db: AsyncSession, product_id: str, admin_id: str) -> bool:
        """Soft delete product. `is_active: False` is the single source of truth for
        visibility — there is no separate `is_deleted` flag."""
        current = await ProductService.get_product(db, product_id)
        product = await db.get(Product, product_id)

        product.is_active = False
        product.updated_at = datetime.utcnow()

        # Log audit
        from services.admin_auth import AdminAuditService
        await AdminAuditService.log_action(
            db,
            admin_id=admin_id,
            admin_name="System",
            action="delete_product",
            entity_type="product",
            entity_id=product_id,
            changes={"is_active": {"old": current.get("is_active", True), "new": False}},
            ip_address="0.0.0.0"
        )

        logger.info(f"Product soft deleted: {product_id} by admin {admin_id}")
        return True

    @staticmethod
    async def list_products(
        db: AsyncSession,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> tuple:
        """List products with filtering"""
        query = select(Product)
        count_query = select(func.count()).select_from(Product)

        if category:
            query = query.where(Product.category == category)
            count_query = count_query.where(Product.category == category)
        if is_active is not None:
            query = query.where(Product.is_active == is_active)
            count_query = count_query.where(Product.is_active == is_active)

        query = query.order_by(Product.created_at.desc()).offset(skip).limit(limit)

        result = await db.execute(query)
        products = result.scalars().all()

        if products:
            ids = [p.id for p in products]
            variant_result = await db.execute(select(ProductVariant).where(ProductVariant.product_id.in_(ids)))
            variants_by_product: dict = {}
            for v in variant_result.scalars().all():
                variants_by_product.setdefault(v.product_id, []).append(_variant_to_dict(v))
        else:
            variants_by_product = {}

        out = []
        for p in products:
            out.append({
                "id": p.id, "name": p.name, "description": p.description, "category": p.category,
                "price": p.price, "discount_percentage": p.discount_percentage,
                "discount_price": p.price * (1 - p.discount_percentage / 100),
                "variants": variants_by_product.get(p.id, []),
                "tags": p.tags or [], "images": p.images or [], "total_stock": p.total_stock,
                "is_active": p.is_active, "created_at": p.created_at, "updated_at": p.updated_at,
                "created_by": p.created_by, "rating": p.rating, "review_count": p.review_count,
            })

        total = (await db.execute(count_query)).scalar_one()
        return out, total

    @staticmethod
    async def get_low_stock_items(db: AsyncSession, threshold: int = 10) -> List[dict]:
        """Get products with low stock"""
        result = await db.execute(
            select(Product).where(Product.is_active == True, Product.total_stock <= threshold)  # noqa: E712
        )
        products = result.scalars().all()
        return [await _product_to_dict(db, p) for p in products]


class InventoryService:
    """Inventory management service"""

    @staticmethod
    async def decrement_variant_stock(db: AsyncSession, product_id: str, size: str, color: str, quantity: int) -> bool:
        """Atomically decrement stock for the variant matching (size, color).

        `UPDATE ... WHERE stock >= :qty` is always a locking read under InnoDB (even at
        REPEATABLE READ), so concurrent checkouts of the same variant correctly serialize on
        that row — same atomicity guarantee the old Mongo elemMatch+positional-$ update gave.
        Returns False if no variant with enough stock matched.
        """
        result = await db.execute(
            update(ProductVariant)
            .where(
                ProductVariant.product_id == product_id,
                ProductVariant.size == size,
                ProductVariant.color == color,
                ProductVariant.stock >= quantity,
            )
            .values(stock=ProductVariant.stock - quantity)
        )
        if result.rowcount == 0:
            return False
        await db.execute(
            update(Product).where(Product.id == product_id)
            .values(total_stock=Product.total_stock - quantity)
        )
        return True

    @staticmethod
    async def restore_variant_stock(db: AsyncSession, product_id: str, size: str, color: str, quantity: int) -> bool:
        """Atomically restore stock for the variant matching (size, color) — used on cancel."""
        result = await db.execute(
            update(ProductVariant)
            .where(
                ProductVariant.product_id == product_id,
                ProductVariant.size == size,
                ProductVariant.color == color,
            )
            .values(stock=ProductVariant.stock + quantity)
        )
        if result.rowcount == 0:
            return False
        await db.execute(
            update(Product).where(Product.id == product_id)
            .values(total_stock=Product.total_stock + quantity)
        )
        return True

    @staticmethod
    async def adjust_stock(
        db: AsyncSession,
        product_id: str,
        variant_sku: str,
        quantity_change: int,
        reason: str,
        admin_id: str,
    ) -> bool:
        """Adjust stock for a variant"""
        result = await db.execute(
            select(ProductVariant).where(ProductVariant.product_id == product_id, ProductVariant.sku == variant_sku)
        )
        variant = result.scalar_one_or_none()

        if not variant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Variant not found"
            )

        new_stock = variant.stock + quantity_change

        if new_stock < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reduce stock below 0"
            )

        variant.stock = new_stock

        await db.execute(
            update(Product).where(Product.id == product_id).values(
                total_stock=Product.total_stock + quantity_change,
                updated_at=datetime.utcnow(),
            )
        )

        db.add(InventoryHistoryEntry(
            product_id=product_id,
            variant_sku=variant_sku,
            quantity_changed=quantity_change,
            reason=reason,
            admin_id=admin_id,
            timestamp=datetime.utcnow(),
        ))

        logger.info(f"Stock adjusted for {variant_sku}: {quantity_change} ({reason})")
        return True

    @staticmethod
    async def get_inventory_history(db: AsyncSession, product_id: str, limit: int = 100) -> dict:
        """Get inventory history for product"""
        result = await db.execute(
            select(InventoryHistoryEntry)
            .where(InventoryHistoryEntry.product_id == product_id)
            .order_by(InventoryHistoryEntry.timestamp.desc())
            .limit(limit)
        )
        entries = result.scalars().all()

        total_result = await db.execute(
            select(func.count()).select_from(InventoryHistoryEntry).where(InventoryHistoryEntry.product_id == product_id)
        )
        total = total_result.scalar_one()

        logs = [
            {
                "product_id": e.product_id, "variant_sku": e.variant_sku,
                "quantity_changed": e.quantity_changed, "reason": e.reason,
                "admin_id": e.admin_id, "timestamp": e.timestamp,
            }
            for e in entries
        ]
        return {"product_id": product_id, "logs": logs, "total_logs": total}
