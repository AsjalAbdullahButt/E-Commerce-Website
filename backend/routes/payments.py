from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db.order import Order
from middleware.auth_middleware import get_current_user
from schemas.payment import PaymentInitiateRequest, PaymentInitiateResponse, PaymentStatusResponse
from services.payment import PaymentService
from utils.ids import is_valid_id
from utils.limiter import limiter
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/{order_id}/initiate", response_model=PaymentInitiateResponse)
@limiter.limit("10/minute")
async def initiate_payment(
    request: Request, order_id: str, body: PaymentInitiateRequest,
    user=Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Start a payment attempt for an order. Never returns a "succeeded" state itself — a
    gateway's own signature-verified webhook (POST /payments/webhook/{gateway}) is the only
    thing that can mark a payment paid."""
    if not is_valid_id(order_id):
        raise HTTPException(status_code=400, detail="Invalid order ID")

    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    idempotency_key = request.headers.get("Idempotency-Key") or body.idempotency_key
    return await PaymentService.initiate_payment(db, order, body.gateway, idempotency_key, str(user["_id"]))


@router.post("/webhook/{gateway}")
@limiter.limit("30/minute")
async def payment_webhook(request: Request, gateway: str, db: AsyncSession = Depends(get_db)):
    """Public gateway callback — no auth (gateways can't hold our JWTs). Every payload is
    signature-verified server-side by the matching gateway's verify_webhook() before anything is
    trusted; an unverified or malformed payload is rejected, never used to mark a payment paid."""
    body = await request.body()
    params = dict(request.query_params)
    try:
        form = await request.form()
        params.update({k: str(v) for k, v in form.items()})
    except Exception:
        pass  # non-form payloads (e.g. Stripe's JSON) are read from `body` inside the gateway

    return await PaymentService.handle_webhook(db, gateway.lower(), dict(request.headers), body, params)


@router.get("/{order_id}/status", response_model=PaymentStatusResponse)
@limiter.limit("30/minute")
async def payment_status(
    request: Request, order_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Poll target for the frontend after a redirect back from a gateway — the redirect itself is
    UX only and is never treated as proof of payment."""
    if not is_valid_id(order_id):
        raise HTTPException(status_code=400, detail="Invalid order ID")

    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if user["role"] == "customer" and order.user_id != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Access denied")

    return await PaymentService.get_status(db, order)
