from fastapi import APIRouter, HTTPException, Depends, Request
from database import orders_col
from models.order import OrderStatusUpdate
from middleware.auth_middleware import require_rider
from utils.limiter import limiter
from datetime import datetime
from bson import ObjectId

router = APIRouter()

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
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid order ID")
    history_entry = {"status": body.status, "timestamp": datetime.utcnow().isoformat(), "note": body.note or ""}
    await orders_col.update_one(
        {"_id": oid},
        {"$set": {"status": body.status}, "$push": {"status_history": history_entry}},
    )
    return {"message": "Status updated"}
