from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db.order import Order, OrderStatusHistory
from db.rider import Rider
from models.order import OrderStatusUpdate
from schemas.rider import RiderProfileUpdate
from middleware.auth_middleware import require_rider
from utils.limiter import limiter
from utils.logger import get_logger, log_to_db
from utils.order_transitions import assert_valid_transition
from utils.ids import is_valid_id
from services.order_user import _order_to_dict

logger = get_logger(__name__)

router = APIRouter()
RIDER_DELIVERY_FEE = 100

@router.get("/orders")
@limiter.limit("30/minute")
async def rider_orders(request: Request, user=Depends(require_rider), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Order).where(
            Order.rider_id == str(user["_id"]),
            Order.status.in_(["shipped", "confirmed", "packed"]),
        )
    )
    orders = result.scalars().all()
    return [await _order_to_dict(db, o) for o in orders]


@router.patch("/orders/{order_id}/status")
@limiter.limit("20/minute")
async def update_delivery_status(request: Request, order_id: str, body: OrderStatusUpdate, user=Depends(require_rider), db: AsyncSession = Depends(get_db)):
    if body.status not in ["shipped", "delivered"]:
        raise HTTPException(status_code=400, detail="Rider can only set shipped or delivered")
    if not is_valid_id(order_id):
        await log_to_db("INVALID_ORDER_ID", __name__, f"rider {str(user['_id'])} tried invalid order ID {order_id}", {"error": "invalid id format", "user_id": str(user["_id"])})
        raise HTTPException(status_code=400, detail="Invalid order ID")

    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.rider_id != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Not assigned to this order")
    assert_valid_transition(order.status, body.status)

    order.status = body.status
    order.updated_at = datetime.utcnow()
    db.add(OrderStatusHistory(order_id=order_id, status=body.status, timestamp=datetime.utcnow(), note=body.note or ""))
    return {"message": "Status updated"}


@router.get("/profile")
@limiter.limit("20/minute")
async def get_profile(request: Request, user=Depends(require_rider), db: AsyncSession = Depends(get_db)):
    rider = await db.get(Rider, user["_id"])
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")
    data = {c.name: getattr(rider, c.name) for c in Rider.__table__.columns}
    data.pop("password", None)
    return {"success": True, "data": data}


@router.patch("/profile")
@limiter.limit("20/minute")
async def update_profile(request: Request, body: RiderProfileUpdate, user=Depends(require_rider), db: AsyncSession = Depends(get_db)):
    rider = await db.get(Rider, user["_id"])
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")
    updated = False
    if body.name:
        rider.name = body.name
        updated = True
    if body.phone:
        rider.phone = body.phone
        updated = True
    if not updated:
        raise HTTPException(status_code=400, detail="No updates provided")
    rider.updated_at = datetime.utcnow()
    return {"success": True, "message": "Profile updated"}


@router.patch("/status")
@limiter.limit("30/minute")
async def set_status(request: Request, status: str = Query(..., pattern="^(available|busy|offline)$"), user=Depends(require_rider), db: AsyncSession = Depends(get_db)):
    rider = await db.get(Rider, user["_id"])
    if rider:
        rider.status = status
        rider.updated_at = datetime.utcnow()
    return {"success": True, "status": status}

@router.get("/earnings")
@limiter.limit("30/minute")
async def get_earnings(request: Request, user=Depends(require_rider), db: AsyncSession = Depends(get_db)):
    """Get rider earnings and delivery statistics"""
    try:
        rider = await db.get(Rider, user["_id"])
        if not rider:
            raise HTTPException(status_code=404, detail="Rider not found")

        rider_id = str(user["_id"])

        total_deliveries = (await db.execute(
            select(func.count()).select_from(Order).where(Order.rider_id == rider_id, Order.status == "delivered")
        )).scalar_one()

        delivery_fee = RIDER_DELIVERY_FEE
        total_earnings = total_deliveries * delivery_fee

        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        this_month = (await db.execute(
            select(func.count()).select_from(Order).where(
                Order.rider_id == rider_id, Order.status == "delivered", Order.created_at >= month_start
            )
        )).scalar_one()

        this_month_earnings = this_month * delivery_fee

        await log_to_db("EARNINGS_VIEW", __name__, f"rider {rider_id} viewed earnings", {"user_id": rider_id})

        return {
            "success": True,
            "data": {
                "total_deliveries": total_deliveries,
                "total_earnings": total_earnings,
                "this_month_deliveries": this_month,
                "this_month_earnings": this_month_earnings,
                "delivery_fee_per_order": delivery_fee,
                "status": rider.status or "offline"
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_to_db("EARNINGS_ERROR", __name__, f"failed to fetch earnings for rider {str(user['_id'])}", {"error": str(e), "user_id": str(user["_id"])})
        logger.error(f"Earnings fetch error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch earnings")

@router.post("/orders/{order_id}/complete")
@limiter.limit("20/minute")
async def complete_delivery(request: Request, order_id: str, proof_image_url: str = None, user=Depends(require_rider), db: AsyncSession = Depends(get_db)):
    """Mark delivery as completed by rider. `proof_image_url` is accepted for API compatibility
    but never populated by any current frontend caller (confirmed via grep) — not persisted."""
    if not is_valid_id(order_id):
        await log_to_db("INVALID_ORDER_ID", __name__, f"rider {str(user['_id'])} tried invalid order ID {order_id}", {"error": "invalid id format", "user_id": str(user["_id"])})
        raise HTTPException(status_code=400, detail="Invalid order ID")

    order = await db.get(Order, order_id)
    if not order:
        await log_to_db("ORDER_NOT_FOUND", __name__, f"delivery completion order not found {order_id}", {"user_id": str(user["_id"])})
        raise HTTPException(status_code=404, detail="Order not found")

    # Only rider assigned to this order can complete it
    if order.rider_id != str(user["_id"]):
        await log_to_db("UNAUTHORIZED_DELIVERY", __name__, f"rider {str(user['_id'])} tried to complete order {order_id} assigned to {order.rider_id}", {"order_id": order_id, "user_id": str(user["_id"])})
        raise HTTPException(status_code=403, detail="Not assigned to this order")

    assert_valid_transition(order.status, "delivered")

    try:
        order.status = "delivered"
        order.updated_at = datetime.utcnow()
        db.add(OrderStatusHistory(order_id=order_id, status="delivered", timestamp=datetime.utcnow(), note="Delivered by rider"))

        await log_to_db("DELIVERY_COMPLETED", __name__, f"rider {str(user['_id'])} completed delivery {order_id}", {"order_id": order_id, "user_id": str(user["_id"])})

        return {
            "success": True,
            "message": "Delivery marked as completed"
        }
    except Exception as e:
        await log_to_db("DELIVERY_COMPLETE_ERROR", __name__, f"failed to complete delivery {order_id}", {"error": str(e), "order_id": order_id, "user_id": str(user["_id"])})
        logger.error(f"Delivery completion error: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete delivery")

@router.get("/stats")
@limiter.limit("20/minute")
async def rider_stats(request: Request, user=Depends(require_rider), db: AsyncSession = Depends(get_db)):
    rider_id = str(user["_id"])
    delivered = (await db.execute(
        select(func.count()).select_from(Order).where(Order.rider_id == rider_id, Order.status == "delivered")
    )).scalar_one()
    active = (await db.execute(
        select(func.count()).select_from(Order).where(
            Order.rider_id == rider_id, Order.status.notin_(["delivered", "cancelled", "returned"])
        )
    )).scalar_one()
    earnings = delivered * RIDER_DELIVERY_FEE
    return {"delivered": delivered, "active": active, "earnings": earnings}


@router.get("/orders/history")
@limiter.limit("20/minute")
async def orders_history(request: Request, limit: int = 50, user=Depends(require_rider), db: AsyncSession = Depends(get_db)):
    rider_id = str(user["_id"])
    result = await db.execute(
        select(Order).where(Order.rider_id == rider_id, Order.status == "delivered").order_by(Order.created_at.desc()).limit(limit)
    )
    orders = result.scalars().all()
    return {"data": [await _order_to_dict(db, o) for o in orders]}
