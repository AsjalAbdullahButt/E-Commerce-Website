from fastapi import APIRouter, HTTPException, Depends, Request
from database import reviews_col, products_col, orders_col
from models.review import ReviewCreate
from middleware.auth_middleware import get_current_user
from utils.limiter import limiter
from utils.logger import get_logger, log_to_db
from datetime import datetime
from bson import ObjectId

logger = get_logger(__name__)

router = APIRouter()

@router.post("")
@limiter.limit("5/minute")
async def add_review(request: Request, body: ReviewCreate, user=Depends(get_current_user)):
    """Add review — user must have a delivered order containing the product."""
    order = await orders_col.find_one({
        "user_id":          str(user["_id"]),
        "status":           "delivered",
        "items.product_id": body.product_id,
    })
    if not order:
        raise HTTPException(status_code=403, detail="You can only review products you have purchased and received")

    existing = await reviews_col.find_one({"product_id": body.product_id, "user_id": str(user["_id"])})
    if existing:
        raise HTTPException(status_code=400, detail="You have already reviewed this product")

    doc = {
        **body.dict(),
        "user_id":    str(user["_id"]),
        "user_name":  user["name"],
        "created_at": datetime.utcnow(),
    }
    await reviews_col.insert_one(doc)

    all_reviews = await reviews_col.find({"product_id": body.product_id}).to_list(length=1000)
    if all_reviews:
        avg = sum(r["rating"] for r in all_reviews) / len(all_reviews)
        try:
            await products_col.update_one(
                {"_id": ObjectId(body.product_id)},
                {"$set": {"rating": round(avg, 1), "review_count": len(all_reviews)}},
            )
        except Exception as e:
            await log_to_db("REVIEW_RATING_UPDATE_ERROR", __name__, f"failed to update product rating for {body.product_id}", {"error": str(e), "user_id": str(user["_id"])})

    return {"message": "Review submitted"}

@router.get("/{product_id}")
@limiter.limit("60/minute")
async def get_reviews(request: Request, product_id: str):
    """Get reviews for a product."""
    reviews = await reviews_col.find({"product_id": product_id}).sort("created_at", -1).to_list(length=50)
    for r in reviews:
        r["id"] = str(r.pop("_id"))
    return reviews
