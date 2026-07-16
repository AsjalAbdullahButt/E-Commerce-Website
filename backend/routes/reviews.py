from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db.order import Order, OrderItem
from db.product import Product
from db.review import Review
from models.review import ReviewCreate
from middleware.auth_middleware import get_current_user
from utils.limiter import limiter
from utils.logger import get_logger, log_to_db

logger = get_logger(__name__)

router = APIRouter()

@router.post("")
@limiter.limit("5/minute")
async def add_review(request: Request, body: ReviewCreate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Add review — user must have a delivered order containing the product."""
    order_result = await db.execute(
        select(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .where(
            Order.user_id == str(user["_id"]),
            Order.status == "delivered",
            OrderItem.product_id == body.product_id,
        )
        .limit(1)
    )
    if not order_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="You can only review products you have purchased and received")

    existing = await db.execute(
        select(Review).where(Review.product_id == body.product_id, Review.user_id == str(user["_id"]))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You have already reviewed this product")

    db.add(Review(
        product_id=body.product_id, rating=body.rating, comment=body.comment,
        user_id=str(user["_id"]), user_name=user["name"], created_at=datetime.utcnow(),
    ))
    await db.flush()

    agg_result = await db.execute(
        select(func.avg(Review.rating), func.count()).where(Review.product_id == body.product_id)
    )
    avg, count = agg_result.one()
    if count:
        try:
            product = await db.get(Product, body.product_id)
            if product:
                product.rating = round(avg, 1)
                product.review_count = count
        except Exception as e:
            await log_to_db("REVIEW_RATING_UPDATE_ERROR", __name__, f"failed to update product rating for {body.product_id}", {"error": str(e), "user_id": str(user["_id"])})

    return {"message": "Review submitted"}

@router.get("/{product_id}")
@limiter.limit("60/minute")
async def get_reviews(request: Request, product_id: str, db: AsyncSession = Depends(get_db)):
    """Get reviews for a product."""
    result = await db.execute(
        select(Review).where(Review.product_id == product_id).order_by(Review.created_at.desc()).limit(50)
    )
    reviews = result.scalars().all()
    return [
        {"id": r.id, "product_id": r.product_id, "user_id": r.user_id, "user_name": r.user_name,
         "rating": r.rating, "comment": r.comment, "created_at": r.created_at}
        for r in reviews
    ]
