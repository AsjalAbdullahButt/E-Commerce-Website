from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db.product import Product, ProductVariant
from db.wishlist import WishlistItem
from middleware.auth_middleware import get_current_user
from utils.limiter import limiter

router = APIRouter()

@router.get("")
@limiter.limit("30/minute")
async def get_wishlist(request: Request, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    items_result = await db.execute(select(WishlistItem).where(WishlistItem.user_id == str(user["_id"])))
    items = items_result.scalars().all()
    product_ids = [i.product_id for i in items]
    if not product_ids:
        return []

    products_result = await db.execute(select(Product).where(Product.id.in_(product_ids)))
    products = products_result.scalars().all()

    variants_result = await db.execute(select(ProductVariant).where(ProductVariant.product_id.in_(product_ids)))
    variants_by_product: dict = {}
    for v in variants_result.scalars().all():
        variants_by_product.setdefault(v.product_id, []).append({"size": v.size, "color": v.color, "sku": v.sku, "stock": v.stock})

    return [
        {
            "id": p.id, "name": p.name, "description": p.description, "category": p.category,
            "price": p.price, "discount_percentage": p.discount_percentage,
            "variants": variants_by_product.get(p.id, []), "tags": p.tags or [], "images": p.images or [],
            "is_active": p.is_active, "total_stock": p.total_stock, "rating": p.rating,
            "review_count": p.review_count, "created_at": p.created_at, "updated_at": p.updated_at,
        }
        for p in products
    ]

@router.post("/{product_id}")
@limiter.limit("20/minute")
async def add_to_wishlist(request: Request, product_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(WishlistItem).where(WishlistItem.user_id == str(user["_id"]), WishlistItem.product_id == product_id)
    )
    if not existing.scalar_one_or_none():
        db.add(WishlistItem(user_id=str(user["_id"]), product_id=product_id, added_at=datetime.now(timezone.utc)))
    return {"message": "Added to wishlist"}

@router.delete("/{product_id}")
@limiter.limit("20/minute")
async def remove_from_wishlist(request: Request, product_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(
        delete(WishlistItem).where(WishlistItem.user_id == str(user["_id"]), WishlistItem.product_id == product_id)
    )
    return {"message": "Removed from wishlist"}
