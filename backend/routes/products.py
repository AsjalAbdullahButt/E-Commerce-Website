from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db.product import Product, ProductVariant
from utils.limiter import limiter
from utils.logger import get_logger, log_to_db
from utils.cache import cache_get, cache_set
from utils.ids import is_valid_id
from schemas.product import ProductListResponse, ProductResponse

# NOTE: product writes (create/update/delete) live exclusively under /admin/products
# (routes/admin.py -> services/product.py::ProductService), which enforces the granular
# permission matrix in utils/permissions.py. This router is intentionally read-only so there
# is exactly one write path for the `products` table — see NOTES_schema_audit.md §1.

logger = get_logger(__name__)

router = APIRouter()

@router.get("/categories")
@limiter.limit("60/minute")
async def get_categories(request: Request, db: AsyncSession = Depends(get_db)):
    """Get unique product categories (public, no auth required)"""
    cache_key = "products:categories"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    result = await db.execute(select(Product.category).distinct())
    categories = [row[0] for row in result.all()]
    payload = {"categories": sorted(categories) if categories else []}
    await cache_set(cache_key, payload, ttl_seconds=300)
    return payload

@router.get("", response_model=ProductListResponse)
@limiter.limit("60/minute")
async def list_products(
    request: Request,
    search: str   = Query(""),
    category: str = Query(""),
    sort: str     = Query("newest"),
    page: int     = Query(1,  ge=1),
    limit: int    = Query(12, ge=1, le=100),   # ← hard cap: prevents DB dump
    db: AsyncSession = Depends(get_db),
):
    """List active products with filters, pagination, and rate limiting."""
    # Guard: cap search length to prevent excessive LIKE scans
    if len(search) > 100:
        raise HTTPException(status_code=400, detail="Search query too long (max 100 chars)")

    cache_key = f"products:list:{search}:{category}:{sort}:{page}:{limit}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    query = select(Product).where(Product.is_active == True)  # noqa: E712
    count_query = select(Product).where(Product.is_active == True)  # noqa: E712

    if search:
        # MySQL's default utf8mb4_*_ci collation is already case-insensitive, no LOWER() needed.
        pattern = f"%{search}%"
        query = query.where(Product.name.like(pattern))
        count_query = count_query.where(Product.name.like(pattern))
    if category:
        query = query.where(Product.category == category)
        count_query = count_query.where(Product.category == category)

    sort_map = {
        "newest":     Product.created_at.desc(),
        "price_asc":  Product.price.asc(),
        "price_desc": Product.price.desc(),
        "rating":     Product.rating.desc(),
    }

    skip = (page - 1) * limit
    query = query.order_by(sort_map.get(sort, Product.created_at.desc())).offset(skip).limit(limit)

    result = await db.execute(query)
    products = result.scalars().all()

    total = (await db.execute(select(func.count()).select_from(count_query.subquery()))).scalar_one()
    pages = -(-total // limit)   # ceiling division

    serialized = [await _serialize(db, p) for p in products]

    payload = {"products": serialized, "total": total, "page": page, "pages": pages}
    await cache_set(cache_key, payload, ttl_seconds=30)
    return payload

async def _serialize(db: AsyncSession, p: Product) -> dict:
    result = await db.execute(select(ProductVariant).where(ProductVariant.product_id == p.id))
    variants = [{"size": v.size, "color": v.color, "sku": v.sku, "stock": v.stock} for v in result.scalars().all()]
    return {
        "id": p.id, "name": p.name, "description": p.description, "category": p.category,
        "price": p.price, "discount_percentage": p.discount_percentage, "variants": variants,
        "tags": p.tags or [], "images": p.images or [], "is_active": p.is_active,
        "total_stock": p.total_stock, "rating": p.rating, "review_count": p.review_count,
        "created_at": p.created_at, "updated_at": p.updated_at,
    }

@router.get("/{product_id}", response_model=ProductResponse)
@limiter.limit("120/minute")
async def get_product(request: Request, product_id: str, db: AsyncSession = Depends(get_db)):
    """Get single product by ID."""
    if not is_valid_id(product_id):
        await log_to_db("INVALID_PRODUCT_ID", __name__, f"invalid product ID {product_id}", {})
        raise HTTPException(status_code=400, detail="Invalid product ID")
    p = await db.get(Product, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return await _serialize(db, p)
