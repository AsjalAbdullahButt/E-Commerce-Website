from fastapi import APIRouter, HTTPException, Query, Request
from database import products_col
from utils.limiter import limiter
from utils.logger import get_logger, log_to_db
from utils.cache import cache_get, cache_set
from bson import ObjectId
import re
from schemas.product import ProductListResponse, ProductResponse

# NOTE: product writes (create/update/delete) live exclusively under /admin/products
# (routes/admin.py -> services/product.py::ProductService), which enforces the granular
# permission matrix in utils/permissions.py. This router is intentionally read-only so there
# is exactly one write path for the `products` collection — see NOTES_schema_audit.md §1.

logger = get_logger(__name__)

router = APIRouter()

def serialize(p: dict) -> dict:
    """Return a safe copy with string id — never mutate in place."""
    result = dict(p)
    result["id"] = str(result.pop("_id"))
    return result

@router.get("/categories")
@limiter.limit("60/minute")
async def get_categories(request: Request):
    """Get unique product categories (public, no auth required)"""
    cache_key = "products:categories"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    categories = await products_col.find({}).distinct("category")
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
):
    """List active products with filters, pagination, and rate limiting."""
    # Guard: cap search length to prevent ReDoS
    if len(search) > 100:
        raise HTTPException(status_code=400, detail="Search query too long (max 100 chars)")

    cache_key = f"products:list:{search}:{category}:{sort}:{page}:{limit}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    query: dict = {"is_active": True}
    if search:
        safe_search = re.escape(search)
        query["name"] = {"$regex": safe_search, "$options": "i"}
    if category:
        query["category"] = category

    sort_map = {
        "newest":     [("created_at", -1)],
        "price_asc":  [("price",      1)],
        "price_desc": [("price",     -1)],
        "rating":     [("rating",    -1)],
    }

    skip = (page - 1) * limit
    cursor = products_col.find(query) \
        .sort(sort_map.get(sort, [("created_at", -1)])) \
        .skip(skip).limit(limit)

    products = await cursor.to_list(length=limit)
    total    = await products_col.count_documents(query)
    pages    = -(-total // limit)   # ceiling division

    payload = {"products": [serialize(p) for p in products], "total": total, "page": page, "pages": pages}
    await cache_set(cache_key, payload, ttl_seconds=30)
    return payload

@router.get("/{product_id}", response_model=ProductResponse)
@limiter.limit("120/minute")
async def get_product(request: Request, product_id: str):
    """Get single product by ID."""
    try:
        p = await products_col.find_one({"_id": ObjectId(product_id)})
    except Exception as e:
        await log_to_db("INVALID_PRODUCT_ID", __name__, f"invalid product ID {product_id}", {"error": str(e)})
        raise HTTPException(status_code=400, detail="Invalid product ID")
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return serialize(p)
