from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from db.order import Order
from middleware.auth_middleware import get_current_user_optional
from schemas.payment import (
    PaymentInitiateRequest, PaymentInitiateResponse, PaymentMethodsResponse, PaymentStatusResponse,
)
from services.payment import PaymentService
from utils.ids import is_valid_id
from utils.limiter import limiter
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/methods", response_model=PaymentMethodsResponse)
@limiter.limit("60/minute")
async def payment_methods(request: Request):
    """Public — which payment methods are actually usable right now, so the storefront never
    offers one that would just 503 (every gateway defaults off with no real credentials)."""
    return PaymentService.available_methods()


@router.post("/{order_id}/initiate", response_model=PaymentInitiateResponse)
@limiter.limit("10/minute")
async def initiate_payment(
    request: Request, order_id: str, body: PaymentInitiateRequest,
    user=Depends(get_current_user_optional), db: AsyncSession = Depends(get_db),
):
    """Start a payment attempt for an order — logged-in owner, or anyone for a guest order (no
    account to check ownership against; same trust model as the guest order lookup on
    GET /orders/{id}?email=..., which also just trusts knowledge of the order_id). Never returns
    a "succeeded" state itself — a gateway's own signature-verified webhook
    (POST /payments/webhook/{gateway}) is the only thing that can mark a payment paid."""
    if not is_valid_id(order_id):
        raise HTTPException(status_code=400, detail="Invalid order ID")

    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    idempotency_key = request.headers.get("Idempotency-Key") or body.idempotency_key
    requester_id = str(user["_id"]) if user else None
    return await PaymentService.initiate_payment(db, order, body.gateway, idempotency_key, requester_id)


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


@router.api_route("/return/{gateway}", methods=["GET", "POST"])
@limiter.limit("30/minute")
async def payment_return(request: Request, gateway: str, db: AsyncSession = Depends(get_db)):
    """Where a customer's browser lands back after JazzCash/EasyPaisa's hosted checkout page —
    set as pp_ReturnURL / postBackURL in services/gateways/*. This is a "thank you page"
    redirect only: it looks up which order the gateway's own reference field belongs to purely
    to send the browser to the right tracking page, and NEVER marks anything paid — that's
    exclusively POST /payments/webhook/{gateway}'s job, verified server-to-server."""
    params = dict(request.query_params)
    try:
        form = await request.form()
        params.update({k: str(v) for k, v in form.items()})
    except Exception:
        pass

    order_id = await PaymentService.resolve_order_id_for_return(db, gateway.lower(), params)
    target = f"{settings.frontend_url}/customer/tracking.html"
    if order_id:
        target += f"?id={order_id}"
    return RedirectResponse(url=target, status_code=303)


@router.get("/{order_id}/status", response_model=PaymentStatusResponse)
@limiter.limit("30/minute")
async def payment_status(
    request: Request, order_id: str, user=Depends(get_current_user_optional), db: AsyncSession = Depends(get_db),
):
    """Poll target for the frontend after a redirect back from a gateway — the redirect itself is
    UX only and is never treated as proof of payment."""
    if not is_valid_id(order_id):
        raise HTTPException(status_code=400, detail="Invalid order ID")

    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if user:
        if user["role"] == "customer" and order.user_id != str(user["_id"]):
            raise HTTPException(status_code=403, detail="Access denied")
    elif order.user_id is not None:
        # Not a guest order — an unauthenticated caller has no way to prove ownership of it.
        raise HTTPException(status_code=403, detail="Access denied")

    return await PaymentService.get_status(db, order)
