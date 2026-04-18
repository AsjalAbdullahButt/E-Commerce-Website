from fastapi import APIRouter, Depends, Request
from database import wishlist_col, products_col
from middleware.auth_middleware import get_current_user
from utils.limiter import limiter
from datetime import datetime
from bson import ObjectId

router = APIRouter()

@router.get("")
@limiter.limit("30/minute")
async def get_wishlist(request: Request, user=Depends(get_current_user)):
    items = await wishlist_col.find({"user_id": str(user["_id"])}).to_list(length=100)
    product_ids = [ObjectId(i["product_id"]) for i in items]
    products    = await products_col.find({"_id": {"$in": product_ids}}).to_list(length=100)
    for p in products:
        p["id"] = str(p.pop("_id"))
    return products

@router.post("/{product_id}")
@limiter.limit("20/minute")
async def add_to_wishlist(request: Request, product_id: str, user=Depends(get_current_user)):
    existing = await wishlist_col.find_one({"user_id": str(user["_id"]), "product_id": product_id})
    if not existing:
        await wishlist_col.insert_one({
            "user_id":    str(user["_id"]),
            "product_id": product_id,
            "added_at":   datetime.utcnow().isoformat(),
        })
    return {"message": "Added to wishlist"}

@router.delete("/{product_id}")
@limiter.limit("20/minute")
async def remove_from_wishlist(request: Request, product_id: str, user=Depends(get_current_user)):
    await wishlist_col.delete_one({"user_id": str(user["_id"]), "product_id": product_id})
    return {"message": "Removed from wishlist"}
