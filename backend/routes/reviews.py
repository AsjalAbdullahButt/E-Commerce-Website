from fastapi import APIRouter, HTTPException, Depends
from database import reviews_col, products_col, orders_col
from models.review import ReviewCreate
from middleware.auth_middleware import get_current_user
from datetime import datetime
from bson import ObjectId

router = APIRouter()

@router.post("")
async def add_review(body: ReviewCreate, user=Depends(get_current_user)):
    """Add review to product (user must have purchased and received it)"""
    # Verify user ordered this product
    order = await orders_col.find_one({
        "user_id": str(user["_id"]),
        "status": "delivered",
        "items.product_id": body.product_id
    })
    if not order:
        raise HTTPException(
            status_code=403,
            detail="You can only review products you have purchased and received"
        )
    
    # Check if already reviewed
    existing = await reviews_col.find_one({
        "product_id": body.product_id,
        "user_id": str(user["_id"])
    })
    if existing:
        raise HTTPException(status_code=400, detail="You have already reviewed this product")
    
    doc = {
        **body.dict(),
        "user_id": str(user["_id"]),
        "user_name": user["name"],
        "created_at": datetime.utcnow().isoformat()
    }
    await reviews_col.insert_one(doc)
    
    # Update product rating
    all_reviews = await reviews_col.find(
        {"product_id": body.product_id}
    ).to_list(length=1000)
    
    if all_reviews:
        avg = sum(r["rating"] for r in all_reviews) / len(all_reviews)
        await products_col.update_one(
            {"_id": ObjectId(body.product_id)},
            {
                "$set": {
                    "rating": round(avg, 1),
                    "review_count": len(all_reviews)
                }
            }
        )
    
    return {"message": "Review submitted"}

@router.get("/{product_id}")
async def get_reviews(product_id: str):
    """Get reviews for product"""
    reviews = await reviews_col.find(
        {"product_id": product_id}
    ).sort("created_at", -1).to_list(length=50)
    
    for r in reviews:
        r["id"] = str(r.pop("_id"))
    return reviews
