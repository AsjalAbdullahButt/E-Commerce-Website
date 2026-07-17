from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db.order import Order, OrderItem, OrderStatusHistory
from db.product import Product, ProductVariant
from db.promo import Promo
from models.order import OrderCreate, OrderStatusUpdate
from middleware.auth_middleware import get_current_user, get_current_user_optional, require_admin
from services.email import EmailService
from services.email_templates import order_confirmation_email
from services.order_user import _order_to_dict, notify_order_status_change
from services.product import InventoryService
from services.return_request import submit_return_request
from utils.limiter import limiter
from utils.logger import get_logger, log_to_db
from utils.order_transitions import assert_valid_transition
from utils.ids import is_valid_id
from schemas.order import OrderListResponse, OrderResponse
from schemas.return_request import ReturnRequestCreate, ReturnRequestResponse

logger = get_logger(__name__)

router = APIRouter()

TAX_RATE     = 0.10
DELIVERY_FEE = 250

@router.post("", response_model=OrderResponse)
@limiter.limit("10/minute")
async def place_order(request: Request, body: OrderCreate, user=Depends(get_current_user_optional), db: AsyncSession = Depends(get_db)):
    """Place a new order — logged-in customer or guest (see GUEST CHECKOUT below).

    SECURITY: Prices are fetched from the DB — never trusted from the client.
    A client sending price=1 for a Rs5000 item will be charged the real price.

    Stock decrement, promo increment, and the order insert must all succeed or all fail
    together. Under Mongo this needed an explicit transaction (or a manual compensating
    rollback where sessions weren't available — see NOTES_schema_audit.md §9). Under MySQL,
    one request = one session = one transaction: database.py::get_db() commits on clean exit
    and rolls back on any exception, so a plain HTTPException raised partway through this
    function already undoes every write above it — no manual tracking/rollback list needed.

    IDEMPOTENCY: an optional Idempotency-Key header lets a retried checkout submission (e.g. the
    client times out waiting for a response and resubmits) return the order already created
    instead of double-placing it and double-decrementing stock. See db/order.py::idempotency_key.

    GUEST CHECKOUT: no Authorization header -> `user` is None (get_current_user_optional) and
    `body.guest_email` is required instead — the order is created with user_id=None and
    guest_email set. Order confirmation/status emails go to that address; there's no persistent
    "my orders" list for guests (nothing to key it on without an account), but the order
    returned here is the same shape either way, and the frontend prompts the guest to create an
    account with that email right after checkout (frontend/js/checkout.js).
    """
    if not user and not body.guest_email:
        raise HTTPException(status_code=400, detail="guest_email is required when checking out without an account")

    requester_id = str(user["_id"]) if user else None

    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key:
        idem_query = select(Order).where(Order.idempotency_key == idempotency_key)
        idem_query = idem_query.where(Order.user_id == requester_id) if user else idem_query.where(Order.guest_email == body.guest_email)
        existing = (await db.execute(idem_query)).scalar_one_or_none()
        if existing:
            return await _order_to_dict(db, existing)

    resolved_items = []
    subtotal = 0.0
    discount = 0.0

    for item in body.items:
        # ── CRITICAL: fetch real price from DB ──────────────────────────────
        if not is_valid_id(item.product_id):
            await log_to_db("INVALID_PRODUCT_ID", __name__, f"order placement with invalid ID {item.product_id}", {"error": "invalid id format", "user_id": requester_id})
            raise HTTPException(status_code=400, detail=f"Invalid product ID: {item.product_id}")

        product = await db.get(Product, item.product_id)
        if not product or not product.is_active:
            raise HTTPException(status_code=404, detail=f"Product not found: {item.product_id}")

        variant_result = await db.execute(
            select(ProductVariant).where(
                ProductVariant.product_id == item.product_id,
                ProductVariant.size == item.size,
                ProductVariant.color == item.color,
            )
        )
        variant = variant_result.scalar_one_or_none()
        if not variant:
            raise HTTPException(
                status_code=400,
                detail=f"'{product.name}' has no {item.size}/{item.color} variant",
            )
        if variant.stock < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for '{product.name}' ({item.size}/{item.color}). Available: {variant.stock}",
            )

        # Atomically decrement the matching variant's stock to avoid race conditions
        decremented_ok = await InventoryService.decrement_variant_stock(
            db, item.product_id, item.size, item.color, item.quantity
        )
        if not decremented_ok:
            raise HTTPException(status_code=400, detail=f"Stock was just taken for '{product.name}'. Please refresh.")

        real_price = float(product.price)
        line_total = real_price * item.quantity
        subtotal  += line_total

        resolved_items.append({
            "product_id": item.product_id,
            "name":       product.name,
            "price":      real_price,          # ← always server price
            "quantity":   item.quantity,
            "size":       item.size,
            "color":      item.color,
            "image":      item.image,
        })

    # Apply promo code if provided
    if body.promo_code:
        promo_result = await db.execute(
            select(Promo).where(Promo.code == body.promo_code.upper(), Promo.is_active == True)  # noqa: E712
        )
        promo = promo_result.scalar_one_or_none()
        if not promo:
            raise HTTPException(status_code=400, detail="Invalid or expired promo code")

        if promo.expires_at and promo.expires_at < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Promo code has expired")

        if promo.max_uses and promo.uses >= promo.max_uses:
            raise HTTPException(status_code=400, detail="Promo code usage limit reached")

        min_order = float(promo.min_order or 0)
        if subtotal < min_order:
            raise HTTPException(status_code=400, detail=f"Minimum order of Rs {min_order} required")

        if promo.discount_type == "percentage":
            discount = subtotal * (promo.discount_value / 100)
        else:
            discount = float(promo.discount_value)

        promo.uses += 1

    after_discount = subtotal - discount
    tax            = after_discount * TAX_RATE
    total          = after_discount + tax + DELIVERY_FEE

    payment_method = (body.payment_method or "cod").lower()
    order = Order(
        user_id=requester_id,
        guest_email=None if user else body.guest_email,
        status="pending",
        rider_id=None,
        subtotal=round(subtotal, 2),
        discount=round(discount, 2),
        tax=round(tax, 2),
        delivery_fee=DELIVERY_FEE,
        total=round(total, 2),
        payment_method=payment_method,
        payment_reference=body.payment_reference or None,
        # COD has nothing to process; every other method starts "unpaid" until
        # POST /payments/{order_id}/initiate + a verified gateway webhook resolve it.
        payment_status="not_required" if payment_method == "cod" else "unpaid",
        idempotency_key=idempotency_key,
        promo_code=body.promo_code or None,
        full_name=body.shipping_address.full_name,
        phone=body.shipping_address.phone,
        address=body.shipping_address.address,
        city=body.shipping_address.city,
        postal_code=body.shipping_address.postal_code,
    )
    db.add(order)
    await db.flush()  # populate order.id

    for ri in resolved_items:
        db.add(OrderItem(order_id=order.id, **ri))

    db.add(OrderStatusHistory(order_id=order.id, status="pending", timestamp=datetime.utcnow(), note="Order placed"))
    await db.flush()

    subject, html = order_confirmation_email(order, resolved_items)
    await EmailService.send(
        user["email"] if user else body.guest_email, subject, html,
        event_code="ORDER_CONFIRMATION_EMAIL_SENT", meta={"order_id": order.id},
    )

    return await _order_to_dict(db, order)

@router.get("/me", response_model=OrderListResponse)
@limiter.limit("30/minute")
async def my_orders(request: Request, page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get user's orders."""
    user_id = str(user["_id"])
    total = (await db.execute(select(func.count()).select_from(Order).where(Order.user_id == user_id))).scalar_one()
    skip = (page - 1) * limit
    result = await db.execute(
        select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()).offset(skip).limit(limit)
    )
    orders = result.scalars().all()
    data = [await _order_to_dict(db, o) for o in orders]
    return {"data": data, "total": total, "page": page, "pages": -(-total // limit)}

@router.get("", response_model=OrderListResponse)
@limiter.limit("30/minute")
async def all_orders(request: Request, page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=100), _=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Get all orders (admin only)."""
    total = (await db.execute(select(func.count()).select_from(Order))).scalar_one()
    skip = (page - 1) * limit
    result = await db.execute(select(Order).order_by(Order.created_at.desc()).offset(skip).limit(limit))
    orders = result.scalars().all()
    data = [await _order_to_dict(db, o) for o in orders]
    return {"data": data, "total": total, "page": page, "pages": -(-total // limit)}

@router.get("/{order_id}", response_model=OrderResponse)
@limiter.limit("30/minute")
async def get_order(
    request: Request, order_id: str, email: Optional[str] = Query(None),
    user=Depends(get_current_user_optional), db: AsyncSession = Depends(get_db),
):
    """Get single order — customers can only see their own; a guest order (no account) can only
    be looked up unauthenticated, by also supplying the guest_email it was placed with."""
    if not is_valid_id(order_id):
        await log_to_db("INVALID_ORDER_ID", __name__, f"invalid order ID requested {order_id}", {"error": "invalid id format", "user_id": str(user["_id"]) if user else None})
        raise HTTPException(status_code=400, detail="Invalid order ID")

    o = await db.get(Order, order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")

    if not user:
        if not o.guest_email or not email or email.lower() != o.guest_email.lower():
            raise HTTPException(status_code=403, detail="Access denied")
        return await _order_to_dict(db, o)
    if user["role"] == "customer" and o.user_id != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    return await _order_to_dict(db, o)

@router.patch("/{order_id}/status")
@limiter.limit("20/minute")
async def update_status(request: Request, order_id: str, body: OrderStatusUpdate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Update order status (admin/rider only)."""
    if user["role"] not in ["admin", "rider"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    if not is_valid_id(order_id):
        raise HTTPException(status_code=400, detail="Invalid order ID")

    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    assert_valid_transition(order.status, body.status)

    order.status = body.status
    order.updated_at = datetime.utcnow()
    db.add(OrderStatusHistory(order_id=order_id, status=body.status, timestamp=datetime.utcnow(), note=body.note or ""))
    await notify_order_status_change(db, order, body.status)

    return {"message": "Status updated"}

# NOTE: rider assignment lives at PATCH /admin/orders/{id}/assign-rider (routes/admin.py),
# which validates the rider exists and is active/available and that the order isn't already
# delivered/cancelled — this router no longer has its own unvalidated copy. See
# NOTES_schema_audit.md §4.

@router.post("/{order_id}/cancel")
@limiter.limit("10/minute")
async def cancel_order(request: Request, order_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Cancel a pending order. Customers can only cancel their own orders."""
    if not is_valid_id(order_id):
        await log_to_db("INVALID_ORDER_ID", __name__, f"invalid order ID on cancel {order_id}", {"error": "invalid id format", "user_id": str(user["_id"])})
        raise HTTPException(status_code=400, detail="Invalid order ID")

    order = await db.get(Order, order_id)
    if not order:
        await log_to_db("ORDER_NOT_FOUND", __name__, f"order not found for cancellation {order_id}", {"user_id": str(user["_id"])})
        raise HTTPException(status_code=404, detail="Order not found")

    # Customers can only cancel their own orders
    if user["role"] == "customer" and order.user_id != str(user["_id"]):
        await log_to_db("UNAUTHORIZED_CANCEL", __name__, f"user {str(user['_id'])} tried to cancel another user's order {order_id}", {"order_id": order_id, "user_id": str(user["_id"])})
        raise HTTPException(status_code=403, detail="Cannot cancel another user's order")

    assert_valid_transition(order.status, "cancelled")

    try:
        order.status = "cancelled"
        order.updated_at = datetime.utcnow()
        db.add(OrderStatusHistory(order_id=order_id, status="cancelled", timestamp=datetime.utcnow(), note="Cancelled by user"))
        await notify_order_status_change(db, order, "cancelled")

        # Restore variant stock for items in cancelled order
        items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order_id))
        for it in items_result.scalars().all():
            try:
                restored = await InventoryService.restore_variant_stock(db, it.product_id, it.size, it.color, it.quantity)
                if not restored:
                    await log_to_db("STOCK_RESTORE_FAILED", __name__, "no matching variant to restore stock on cancel", {"order_id": order_id, "item": it.product_id})
            except Exception:
                # Ignore stock restore failures but log
                await log_to_db("STOCK_RESTORE_FAILED", __name__, "failed to restore stock on cancel", {"order_id": order_id, "item": it.product_id})
        await log_to_db("ORDER_CANCELLED", __name__, f"order {order_id} cancelled by user {str(user['_id'])}", {"order_id": order_id, "user_id": str(user["_id"])})
        return {
            "success": True,
            "message": "Order cancelled successfully"
        }
    except Exception as e:
        await log_to_db("ORDER_CANCEL_ERROR", __name__, f"failed to cancel order {order_id}", {"error": str(e), "order_id": order_id, "user_id": str(user["_id"])})
        logger.error(f"Order cancellation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel order")


@router.post("/{order_id}/return-request", response_model=ReturnRequestResponse)
@limiter.limit("5/minute")
async def create_return_request(
    request: Request, order_id: str, body: ReturnRequestCreate, email: Optional[str] = Query(None),
    user=Depends(get_current_user_optional), db: AsyncSession = Depends(get_db),
):
    """Request a return/refund on a delivered order — logged-in owner, or a guest supplying the
    email the order was placed with (same lookup convention as GET /orders/{id}?email=...).
    Only one pending request per order at a time; admin resolves it via
    PATCH /admin/returns/{return_id} (routes/admin.py), which restores stock and transitions the
    order to "returned" on approval."""
    if not is_valid_id(order_id):
        raise HTTPException(status_code=400, detail="Invalid order ID")

    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if not user:
        if not order.guest_email or not email or email.lower() != order.guest_email.lower():
            raise HTTPException(status_code=403, detail="Access denied")
        requester_id = None
    else:
        requester_id = str(user["_id"])

    return await submit_return_request(db, order, requester_id, body.reason)
