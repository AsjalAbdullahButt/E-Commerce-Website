from fastapi import APIRouter, HTTPException, Depends, Query
from database import products_col
from models.product import ProductCreate, ProductUpdate
from middleware.auth_middleware import require_admin
from datetime import datetime
from bson import ObjectId

router = APIRouter()

def serialize(p):
    p["id"] = str(p.pop("_id"))
    return p

@router.get("")
async def list_products(
    search: str = Query(""),
    category: str = Query(""),
    sort: str = Query("newest"),
    page: int = Query(1),
    limit: int = Query(12)
):
    """List all active products with filters"""
    query = {"is_active": True}
    
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    if category:
        query["category"] = category
    
    sort_map = {
        "newest": [("created_at", -1)],
        "price_asc": [("price", 1)],
        "price_desc": [("price", -1)],
        "rating": [("rating", -1)]
    }
    
    skip = (page - 1) * limit
    cursor = products_col.find(query).sort(
        sort_map.get(sort, [("created_at", -1)])
    ).skip(skip).limit(limit)
    
    products = await cursor.to_list(length=limit)
    total = await products_col.count_documents(query)
    pages = -(-total // limit)
    
    return {
        "products": [serialize(p) for p in products],
        "total": total,
        "page": page,
        "pages": pages
    }

@router.get("/{product_id}")
async def get_product(product_id: str):
    """Get single product"""
    try:
        p = await products_col.find_one({"_id": ObjectId(product_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid product ID")
    
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return serialize(p)

@router.post("")
async def create_product(body: ProductCreate, _=Depends(require_admin)):
    """Create new product (admin only)"""
    doc = {
        **body.dict(),
        "rating": 0.0,
        "review_count": 0,
        "is_active": True,
        "created_at": datetime.utcnow().isoformat()
    }
    result = await products_col.insert_one(doc)
    p = await products_col.find_one({"_id": result.inserted_id})
    return serialize(p)

@router.put("/{product_id}")
async def update_product(product_id: str, body: ProductUpdate, _=Depends(require_admin)):
    """Update product (admin only)"""
    try:
        oid = ObjectId(product_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid product ID")
    
    update_data = {k: v for k, v in body.dict().items() if v is not None}
    if not update_data:
        p = await products_col.find_one({"_id": oid})
        return serialize(p) if p else None
    
    await products_col.update_one({"_id": oid}, {"$set": update_data})
    p = await products_col.find_one({"_id": oid})
    return serialize(p)

@router.delete("/{product_id}")
async def delete_product(product_id: str, _=Depends(require_admin)):
    """Deactivate product (admin only)"""
    try:
        oid = ObjectId(product_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid product ID")
    
    await products_col.update_one({"_id": oid}, {"$set": {"is_active": False}})
    return {"message": "Product deactivated"}
