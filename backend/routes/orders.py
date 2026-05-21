from fastapi import APIRouter, HTTPException, Depends, Request
from database import orders_col, promos_col, products_col
from models.order import OrderCreate, OrderStatusUpdate
from middleware.auth_middleware import get_current_user, require_admin, require_rider
from utils.limiter import limiter
from utils.logger import get_logger, log_to_db
from datetime import datetime
from bson import ObjectId
from fastapi import Query
from schemas.order import OrderListResponse, OrderResponse

logger = get_logger(__name__)

router = APIRouter()

def serialize(o: dict) -> dict:
    result = dict(o)
    result["id"] = str(result.pop("_id"))
    return result

TAX_RATE     = 0.10
DELIVERY_FEE = 250

@router.post("", response_model=OrderResponse)
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
        except Exception as e:
            await log_to_db("INVALID_PRODUCT_ID", f"order placement with invalid ID {item.product_id}", {"error": str(e), "user_id": str(user["_id"])})
            raise HTTPException(status_code=400, detail=f"Invalid product ID: {item.product_id}")

        product = await products_col.find_one({"_id": oid, "is_active": True})
        if not product:
            raise HTTPException(status_code=404, detail=f"Product not found: {item.product_id}")

        # Check stock for product (support either 'stock' or 'total_stock')
        available_stock = int(product.get("stock", product.get("total_stock", 0)))
        if available_stock < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for '{product['name']}'. Available: {available_stock}"
            )

        # Atomically decrement stock to avoid race conditions
        stock_update = await products_col.update_one(
            {"_id": oid, "stock": {"$gte": item.quantity}},
            {"$inc": {"stock": -item.quantity}}
        )
        if stock_update.modified_count == 0:
            raise HTTPException(status_code=400, detail=f"Stock was just taken for '{product['name']}'. Please refresh.")

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
            # Robust expiry check: promo.expires_at may be stored as datetime
            expires = promo.get("expires_at")
            if expires:
                if isinstance(expires, str):
                    try:
                        expires = datetime.fromisoformat(expires)
                    except Exception:
                        expires = None
            if expires and expires < datetime.utcnow():
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
        "updated_at": datetime.utcnow().isoformat(),
    }
    result = await orders_col.insert_one(doc)
    order  = await orders_col.find_one({"_id": result.inserted_id})
    return serialize(order)

@router.get("/me", response_model=OrderListResponse)
@limiter.limit("30/minute")
async def my_orders(request: Request, page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), user=Depends(get_current_user)):
    """Get user's orders."""
    query = {"user_id": str(user["_id"])}
    total = await orders_col.count_documents(query)
    skip = (page - 1) * limit
    cursor = orders_col.find(query).sort("created_at", -1).skip(skip).limit(limit)
    orders = await cursor.to_list(length=limit)
    return {"data": [serialize(o) for o in orders], "total": total, "page": page, "pages": -(-total // limit)}

@router.get("", response_model=OrderListResponse)
@limiter.limit("30/minute")
async def all_orders(request: Request, page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=100), _=Depends(require_admin)):
    """Get all orders (admin only)."""
    total = await orders_col.count_documents({})
    skip = (page - 1) * limit
    orders = await orders_col.find({}).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
    return {"data": [serialize(o) for o in orders], "total": total, "page": page, "pages": -(-total // limit)}

@router.get("/{order_id}", response_model=OrderResponse)
@limiter.limit("30/minute")
async def get_order(request: Request, order_id: str, user=Depends(get_current_user)):
    """Get single order — customers can only see their own."""
    try:
        oid = ObjectId(order_id)
    except Exception as e:
        await log_to_db("INVALID_ORDER_ID", f"invalid order ID requested {order_id}", {"error": str(e), "user_id": str(user["_id"])})
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
        {"$set": {"status": body.status, "updated_at": datetime.utcnow().isoformat()}, "$push": {"status_history": history_entry}},
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
    await orders_col.update_one({"_id": oid}, {"$set": {"rider_id": rider_id, "updated_at": datetime.utcnow().isoformat()}})
    return {"message": "Rider assigned"}

@router.post("/{order_id}/cancel")
@limiter.limit("10/minute")
async def cancel_order(request: Request, order_id: str, user=Depends(get_current_user)):
    """Cancel a pending order. Customers can only cancel their own orders."""
    try:
        oid = ObjectId(order_id)
    except Exception as e:
        await log_to_db("INVALID_ORDER_ID", f"invalid order ID on cancel {order_id}", {"error": str(e), "user_id": str(user["_id"])})
        raise HTTPException(status_code=400, detail="Invalid order ID")
    
    order = await orders_col.find_one({"_id": oid})
    if not order:
        await log_to_db("ORDER_NOT_FOUND", f"order not found for cancellation {order_id}", {"user_id": str(user["_id"])})
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Customers can only cancel their own orders
    if user["role"] == "customer" and order["user_id"] != str(user["_id"]):
        await log_to_db("UNAUTHORIZED_CANCEL", f"user {str(user['_id'])} tried to cancel another user's order {order_id}", {"order_id": order_id, "user_id": str(user["_id"])})
        raise HTTPException(status_code=403, detail="Cannot cancel another user's order")
    
    # Only pending orders can be cancelled
    if order["status"] != "pending":
        await log_to_db("INVALID_CANCEL_STATUS", f"attempted to cancel order {order_id} with status {order['status']}", {"order_id": order_id, "user_id": str(user["_id"])})
        raise HTTPException(status_code=400, detail=f"Cannot cancel order with status '{order['status']}'. Only pending orders can be cancelled.")
    
    try:
        history_entry = {
            "status": "cancelled",
            "timestamp": datetime.utcnow().isoformat(),
            "note": "Cancelled by user",
        }
        await orders_col.update_one(
            {"_id": oid},
            {"$set": {"status": "cancelled", "updated_at": datetime.utcnow().isoformat()}, "$push": {"status_history": history_entry}}
        )
        # Restore stock for items in cancelled order
        for it in order.get("items", []):
            try:
                prod_oid = ObjectId(it.get("product_id"))
                await products_col.update_one({"_id": prod_oid}, {"$inc": {"stock": it.get("quantity", 0)}})
            except Exception:
                # Ignore stock restore failures but log
                await log_to_db("STOCK_RESTORE_FAILED", "failed to restore stock on cancel", {"order_id": order_id, "item": it})
        await log_to_db("ORDER_CANCELLED", f"order {order_id} cancelled by user {str(user['_id'])}", {"order_id": str(oid), "user_id": str(user["_id"])})
        return {
            "success": True,
            "message": "Order cancelled successfully"
        }
    except Exception as e:
        await log_to_db("ORDER_CANCEL_ERROR", f"failed to cancel order {order_id}", {"error": str(e), "order_id": str(oid), "user_id": str(user["_id"])})
        logger.error(f"Order cancellation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel order")
