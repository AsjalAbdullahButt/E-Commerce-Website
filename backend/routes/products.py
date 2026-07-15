from fastapi import APIRouter, HTTPException, Depends, Query, Request
from database import products_col
from models.product import ProductCreate, ProductUpdate
from middleware.auth_middleware import require_admin
from utils.limiter import limiter
from utils.logger import get_logger, log_to_db
from utils.cache import cache_get, cache_set, cache_clear_prefix, cache_delete
from datetime import datetime
from bson import ObjectId
import re
from schemas.product import ProductListResponse, ProductResponse

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
        await log_to_db("INVALID_PRODUCT_ID", f"invalid product ID {product_id}", {"error": str(e)})
        raise HTTPException(status_code=400, detail="Invalid product ID")
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return serialize(p)

@router.post("", response_model=ProductResponse)
@limiter.limit("30/minute")
async def create_product(request: Request, body: ProductCreate, _=Depends(require_admin)):
    """Create new product (admin only)."""
    doc = {
        **body.dict(),
        "rating":       0.0,
        "review_count": 0,
        "is_active":    True,
        "created_at":   datetime.utcnow().isoformat(),
        "updated_at":   datetime.utcnow().isoformat(),
    }
    result = await products_col.insert_one(doc)
    p = await products_col.find_one({"_id": result.inserted_id})
    await cache_clear_prefix("products:list:")
    await cache_delete("products:categories")
    return serialize(p)

@router.put("/{product_id}", response_model=ProductResponse)
@limiter.limit("30/minute")
async def update_product(request: Request, product_id: str, body: ProductUpdate, _=Depends(require_admin)):
    """Update product (admin only)."""
    try:
        oid = ObjectId(product_id)
    except Exception as e:
        await log_to_db("INVALID_PRODUCT_ID", f"admin tried to update product with invalid ID {product_id}", {"error": str(e)})
        raise HTTPException(status_code=400, detail="Invalid product ID")

    update_data = {k: v for k, v in body.dict().items() if v is not None}
    if update_data:
        update_data["updated_at"] = datetime.utcnow().isoformat()
        await products_col.update_one({"_id": oid}, {"$set": update_data})
    p = await products_col.find_one({"_id": oid})
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    await cache_clear_prefix("products:list:")
    await cache_delete("products:categories")
    return serialize(p)

@router.delete("/{product_id}")
@limiter.limit("20/minute")
async def delete_product(request: Request, product_id: str, _=Depends(require_admin)):
    """Soft-delete product (admin only)."""
    try:
        oid = ObjectId(product_id)
    except Exception as e:
        await log_to_db("INVALID_PRODUCT_ID", f"admin tried to delete product with invalid ID {product_id}", {"error": str(e)})
        raise HTTPException(status_code=400, detail="Invalid product ID")
    await products_col.update_one({"_id": oid}, {"$set": {"is_active": False, "updated_at": datetime.utcnow().isoformat()}})
    await cache_clear_prefix("products:list:")
    await cache_delete("products:categories")
    return {"message": "Product deactivated"}
