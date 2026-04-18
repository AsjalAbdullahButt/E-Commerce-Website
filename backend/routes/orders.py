from fastapi import APIRouter, HTTPException, Depends
from database import orders_col, promos_col, products_col
from models.order import OrderCreate, OrderStatusUpdate
from middleware.auth_middleware import get_current_user, require_admin, require_rider
from datetime import datetime
from bson import ObjectId

router = APIRouter()

def serialize(o):
    o["id"] = str(o.pop("_id"))
    return o

TAX_RATE     = 0.10
DELIVERY_FEE = 250

@router.post("")
async def place_order(body: OrderCreate, user=Depends(get_current_user)):
    """Place a new order"""
    subtotal = sum(i.price * i.quantity for i in body.items)
    discount = 0.0

    # Apply promo code if provided
    if body.promo_code:
        promo = await promos_col.find_one({
            "code": body.promo_code.upper(),
            "is_active": True
        })
        if promo and subtotal >= promo.get("min_order", 0):
            if promo["discount_type"] == "percentage":
                discount = subtotal * (promo["discount_value"] / 100)
            else:
                discount = promo["discount_value"]
            await promos_col.update_one(
                {"_id": promo["_id"]},
                {"$inc": {"uses": 1}}
            )

    after_discount = subtotal - discount
    tax = after_discount * TAX_RATE
    total = after_discount + tax + DELIVERY_FEE

    doc = {
        "user_id": str(user["_id"]),
        "items": [i.dict() for i in body.items],
        "shipping_address": body.shipping_address.dict(),
        "payment_method": "COD",
        "promo_code": body.promo_code or None,
        "subtotal": subtotal,
        "discount": discount,
        "tax": tax,
        "delivery_fee": DELIVERY_FEE,
        "total": total,
        "status": "pending",
        "rider_id": None,
        "status_history": [{
            "status": "pending",
            "timestamp": datetime.utcnow().isoformat(),
            "note": "Order placed"
        }],
        "created_at": datetime.utcnow().isoformat()
    }
    result = await orders_col.insert_one(doc)
    order = await orders_col.find_one({"_id": result.inserted_id})
    return serialize(order)

@router.get("/me")
async def my_orders(user=Depends(get_current_user)):
    """Get user's orders"""
    cursor = orders_col.find({"user_id": str(user["_id"])}).sort("created_at", -1)
    orders = await cursor.to_list(length=100)
    return [serialize(o) for o in orders]

@router.get("")
async def all_orders(_=Depends(require_admin)):
    """Get all orders (admin only)"""
    orders = await orders_col.find({}).sort("created_at", -1).to_list(length=500)
    return [serialize(o) for o in orders]

@router.get("/{order_id}")
async def get_order(order_id: str, user=Depends(get_current_user)):
    """Get single order"""
    try:
        oid = ObjectId(order_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid order ID")
    
    o = await orders_col.find_one({"_id": oid})
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check authorization: customer can only see own orders
    if user["role"] == "customer" and o["user_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return serialize(o)

@router.patch("/{order_id}/status")
async def update_status(order_id: str, body: OrderStatusUpdate, user=Depends(get_current_user)):
    """Update order status (admin/rider only)"""
    if user["role"] not in ["admin", "rider"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        oid = ObjectId(order_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid order ID")
    
    history_entry = {
        "status": body.status,
        "timestamp": datetime.utcnow().isoformat(),
        "note": body.note or ""
    }
    
    await orders_col.update_one(
        {"_id": oid},
        {
            "$set": {"status": body.status},
            "$push": {"status_history": history_entry}
        }
    )
    return {"message": "Status updated"}

@router.patch("/{order_id}/assign-rider")
async def assign_rider(order_id: str, rider_id: str, _=Depends(require_admin)):
    """Assign rider to order (admin only)"""
    try:
        oid = ObjectId(order_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid order ID")
    
    await orders_col.update_one({"_id": oid}, {"$set": {"rider_id": rider_id}})
    return {"message": "Rider assigned"}
