from fastapi import APIRouter, HTTPException, Depends, Request
from database import orders_col, promos_col, products_col
from models.order import OrderCreate, OrderStatusUpdate
from middleware.auth_middleware import get_current_user, require_admin, require_rider
from utils.limiter import limiter
from datetime import datetime
from bson import ObjectId

router = APIRouter()

def serialize(o: dict) -> dict:
    result = dict(o)
    result["id"] = str(result.pop("_id"))
    return result

TAX_RATE     = 0.10
DELIVERY_FEE = 250

@router.post("")
@limiter.limit("10/minute")
async def place_order(request: Request, body: OrderCreate, user=Depends(get_current_user)):
    """Place a new order.
    
    SECURITY: Prices are fetched from the DB — never trusted from the client.
    A client sending price=1 for a Rs5000 item will be charged the real price.
    """
    resolved_items = []
    subtotal = 0.0

    for item in body.items:
        # ── CRITICAL: fetch real price from DB ──────────────────────────────
        try:
            oid = ObjectId(item.product_id)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid product ID: {item.product_id}")

        product = await products_col.find_one({"_id": oid, "is_active": True})
        if not product:
            raise HTTPException(status_code=404, detail=f"Product not found: {item.product_id}")

        real_price = float(product["price"])
        line_total = real_price * item.quantity
        subtotal  += line_total

        resolved_items.append({
            "product_id": item.product_id,
            "name":       product["name"],
            "price":      real_price,          # ← always server price
            "quantity":   item.quantity,
            "size":       item.size,
            "color":      item.color,
            "image":      item.image,
        })

    discount = 0.0

    # Apply promo code if provided
    if body.promo_code:
        promo = await promos_col.find_one({
            "code":      body.promo_code.upper(),
            "is_active": True,
        })
        if promo and subtotal >= promo.get("min_order", 0):
            if promo.get("expires_at") and promo["expires_at"] < datetime.utcnow().isoformat():
                raise HTTPException(status_code=400, detail="Promo code has expired")
            if promo.get("max_uses") and promo.get("uses", 0) >= promo["max_uses"]:
                raise HTTPException(status_code=400, detail="Promo code usage limit reached")

            if promo["discount_type"] == "percentage":
                discount = subtotal * (promo["discount_value"] / 100)
            else:
                discount = float(promo["discount_value"])

            await promos_col.update_one({"_id": promo["_id"]}, {"$inc": {"uses": 1}})

    after_discount = subtotal - discount
    tax            = after_discount * TAX_RATE
    total          = after_discount + tax + DELIVERY_FEE

    doc = {
        "user_id":           str(user["_id"]),
        "items":             resolved_items,
        "shipping_address":  body.shipping_address.dict(),
        "payment_method":    (body.payment_method or "cod").lower(),
        "payment_reference": body.payment_reference or None,
        "promo_code":        body.promo_code or None,
        "subtotal":          round(subtotal, 2),
        "discount":          round(discount, 2),
        "tax":               round(tax, 2),
        "delivery_fee":      DELIVERY_FEE,
        "total":             round(total, 2),
        "status":            "pending",
        "rider_id":          None,
        "status_history":    [{
            "status":    "pending",
            "timestamp": datetime.utcnow().isoformat(),
            "note":      "Order placed",
        }],
        "created_at": datetime.utcnow().isoformat(),
    }
    result = await orders_col.insert_one(doc)
    order  = await orders_col.find_one({"_id": result.inserted_id})
    return serialize(order)

@router.get("/me")
@limiter.limit("30/minute")
async def my_orders(request: Request, user=Depends(get_current_user)):
    """Get user's orders."""
    cursor = orders_col.find({"user_id": str(user["_id"])}).sort("created_at", -1)
    orders = await cursor.to_list(length=100)
    return [serialize(o) for o in orders]

@router.get("")
@limiter.limit("30/minute")
async def all_orders(request: Request, _=Depends(require_admin)):
    """Get all orders (admin only)."""
    orders = await orders_col.find({}).sort("created_at", -1).to_list(length=500)
    return [serialize(o) for o in orders]

@router.get("/{order_id}")
@limiter.limit("30/minute")
async def get_order(request: Request, order_id: str, user=Depends(get_current_user)):
    """Get single order — customers can only see their own."""
    try:
        oid = ObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid order ID")

    o = await orders_col.find_one({"_id": oid})
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    if user["role"] == "customer" and o["user_id"] != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    return serialize(o)

@router.patch("/{order_id}/status")
@limiter.limit("20/minute")
async def update_status(request: Request, order_id: str, body: OrderStatusUpdate, user=Depends(get_current_user)):
    """Update order status (admin/rider only)."""
    if user["role"] not in ["admin", "rider"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        oid = ObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid order ID")

    history_entry = {
        "status":    body.status,
        "timestamp": datetime.utcnow().isoformat(),
        "note":      body.note or "",
    }
    await orders_col.update_one(
        {"_id": oid},
        {"$set": {"status": body.status}, "$push": {"status_history": history_entry}},
    )
    return {"message": "Status updated"}

@router.patch("/{order_id}/assign-rider")
@limiter.limit("20/minute")
async def assign_rider(request: Request, order_id: str, rider_id: str, _=Depends(require_admin)):
    """Assign rider to order (admin only)."""
    try:
        oid = ObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid order ID")
    await orders_col.update_one({"_id": oid}, {"$set": {"rider_id": rider_id}})
    return {"message": "Rider assigned"}
