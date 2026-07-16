from fastapi import APIRouter, HTTPException, Depends, Request
from database import orders_col
from models.order import OrderStatusUpdate
from schemas.rider import RiderProfileUpdate
from middleware.auth_middleware import require_rider
from utils.limiter import limiter
from utils.logger import get_logger, log_to_db
from utils.order_transitions import assert_valid_transition
from datetime import datetime
from bson import ObjectId
from database import riders_col
from fastapi import Query

logger = get_logger(__name__)

router = APIRouter()
RIDER_DELIVERY_FEE = 100

@router.get("/orders")
@limiter.limit("30/minute")
async def rider_orders(request: Request, user=Depends(require_rider)):
    orders = await orders_col.find({
        "rider_id": str(user["_id"]),
        "status": {"$in": ["shipped", "confirmed", "packed"]},
    }).to_list(length=100)
    for o in orders:
        o["id"] = str(o.pop("_id"))
    return orders




@router.patch("/orders/{order_id}/status")
@limiter.limit("20/minute")
async def update_delivery_status(request: Request, order_id: str, body: OrderStatusUpdate, user=Depends(require_rider)):
    if body.status not in ["shipped", "delivered"]:
        raise HTTPException(status_code=400, detail="Rider can only set shipped or delivered")
    try:
        oid = ObjectId(order_id)
    except Exception as e:
        await log_to_db("INVALID_ORDER_ID", __name__, f"rider {str(user['_id'])} tried invalid order ID {order_id}", {"error": str(e), "user_id": str(user["_id"])})
        raise HTTPException(status_code=400, detail="Invalid order ID")

    order = await orders_col.find_one({"_id": oid})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.get("rider_id") != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Not assigned to this order")
    assert_valid_transition(order["status"], body.status)

    history_entry = {"status": body.status, "timestamp": datetime.utcnow(), "note": body.note or ""}
    await orders_col.update_one(
        {"_id": oid},
        {"$set": {"status": body.status, "updated_at": datetime.utcnow()}, "$push": {"status_history": history_entry}},
    )
    return {"message": "Status updated"}


@router.get("/profile")
@limiter.limit("20/minute")
async def get_profile(request: Request, user=Depends(require_rider)):
    rider = await riders_col.find_one({"_id": ObjectId(user["_id"])})
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")
    rider["id"] = str(rider.pop("_id"))
    return {"success": True, "data": rider}


@router.patch("/profile")
@limiter.limit("20/minute")
async def update_profile(request: Request, body: RiderProfileUpdate, user=Depends(require_rider)):
    updates = {}
    if body.name:
        updates["name"] = body.name
    if body.phone:
        updates["phone"] = body.phone
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    updates["updated_at"] = datetime.utcnow().isoformat()
    await riders_col.update_one({"_id": ObjectId(user["_id"])}, {"$set": updates})
    return {"success": True, "message": "Profile updated"}


@router.patch("/status")
@limiter.limit("30/minute")
async def set_status(request: Request, status: str = Query(..., regex="^(available|busy|offline)$"), user=Depends(require_rider)):
    await riders_col.update_one({"_id": ObjectId(user["_id"])}, {"$set": {"status": status, "updated_at": datetime.utcnow().isoformat()}})
    return {"success": True, "status": status}

@router.get("/earnings")
@limiter.limit("30/minute")
async def get_earnings(request: Request, user=Depends(require_rider)):
    """Get rider earnings and delivery statistics"""
    try:
        rider = await riders_col.find_one({"_id": ObjectId(user["_id"])})
        if not rider:
            raise HTTPException(status_code=404, detail="Rider not found")
        
        # Get delivered orders count and commission
        delivered_orders = await orders_col.find({
            "rider_id": str(user["_id"]),
            "status": "delivered"
        }).to_list(length=1000)
        
        delivery_fee = RIDER_DELIVERY_FEE
        total_deliveries = len(delivered_orders)
        total_earnings = total_deliveries * delivery_fee
        
        # This month's deliveries
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        this_month = await orders_col.count_documents({
            "rider_id": str(user["_id"]),
            "status": "delivered",
            "created_at": {"$gte": month_start}
        })
        
        this_month_earnings = this_month * delivery_fee
        
        await log_to_db("EARNINGS_VIEW", __name__, f"rider {str(user['_id'])} viewed earnings", {"user_id": str(user["_id"])})
        
        return {
            "success": True,
            "data": {
                "total_deliveries": total_deliveries,
                "total_earnings": total_earnings,
                "this_month_deliveries": this_month,
                "this_month_earnings": this_month_earnings,
                "delivery_fee_per_order": delivery_fee,
                "status": rider.get("status", "offline")
            }
        }
    except Exception as e:
        await log_to_db("EARNINGS_ERROR", __name__, f"failed to fetch earnings for rider {str(user['_id'])}", {"error": str(e), "user_id": str(user["_id"])})
        logger.error(f"Earnings fetch error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch earnings")

@router.post("/orders/{order_id}/complete")
@limiter.limit("20/minute")
async def complete_delivery(request: Request, order_id: str, proof_image_url: str = None, user=Depends(require_rider)):
    """Mark delivery as completed by rider"""
    try:
        oid = ObjectId(order_id)
    except Exception as e:
        await log_to_db("INVALID_ORDER_ID", __name__, f"rider {str(user['_id'])} tried invalid order ID {order_id}", {"error": str(e), "user_id": str(user["_id"])})
        raise HTTPException(status_code=400, detail="Invalid order ID")
    
    order = await orders_col.find_one({"_id": oid})
    if not order:
        await log_to_db("ORDER_NOT_FOUND", __name__, f"delivery completion order not found {order_id}", {"user_id": str(user["_id"])})
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Only rider assigned to this order can complete it
    if order.get("rider_id") != str(user["_id"]):
        await log_to_db("UNAUTHORIZED_DELIVERY", __name__, f"rider {str(user['_id'])} tried to complete order {order_id} assigned to {order.get('rider_id')}", {"order_id": order_id, "user_id": str(user["_id"])})
        raise HTTPException(status_code=403, detail="Not assigned to this order")
    
    assert_valid_transition(order.get("status"), "delivered")
    
    try:
        history_entry = {
            "status": "delivered",
            "timestamp": datetime.utcnow(),
            "note": "Delivered by rider",
            "proof_image": proof_image_url
        }

        await orders_col.update_one(
            {"_id": oid},
            {
                "$set": {"status": "delivered", "updated_at": datetime.utcnow()},
                "$push": {"status_history": history_entry}
            }
        )
        
        await log_to_db("DELIVERY_COMPLETED", __name__, f"rider {str(user['_id'])} completed delivery {order_id}", {"order_id": str(oid), "user_id": str(user["_id"])})
        
        return {
            "success": True,
            "message": "Delivery marked as completed"
        }
    except Exception as e:
        await log_to_db("DELIVERY_COMPLETE_ERROR", __name__, f"failed to complete delivery {order_id}", {"error": str(e), "order_id": str(oid), "user_id": str(user["_id"])})
        logger.error(f"Delivery completion error: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete delivery")

@router.get("/stats")
@limiter.limit("20/minute")
async def rider_stats(request: Request, user=Depends(require_rider)):
    rider_id = str(user["_id"])
    delivered = await orders_col.count_documents({"rider_id": rider_id, "status": "delivered"})
    active = await orders_col.count_documents({"rider_id": rider_id, "status": {"$ne": "delivered"}})
    earnings = delivered * RIDER_DELIVERY_FEE
    return {"delivered": delivered, "active": active, "earnings": earnings}


@router.get("/orders/history")
@limiter.limit("20/minute")
async def orders_history(request: Request, limit: int = 50, user=Depends(require_rider)):
    rider_id = str(user["_id"])
    cursor = orders_col.find({"rider_id": rider_id, "status": "delivered"}).sort("created_at", -1).limit(limit)
    orders = await cursor.to_list(length=limit)
    for o in orders:
        o["id"] = str(o.pop("_id"))
    return {"data": orders}
