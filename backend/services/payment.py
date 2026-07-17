from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.order import Order, OrderStatusHistory
from db.payment import Payment
from config import settings
from services.gateways.base import PaymentGateway
from services.gateways.easypaisa_gateway import EasyPaisaGateway
from services.gateways.jazzcash_gateway import JazzCashGateway
from services.gateways.stripe_gateway import StripeGateway
from services.order_user import notify_order_status_change
from utils.ids import is_valid_id
from utils.logger import get_logger, log_to_db
from utils.order_transitions import assert_valid_transition
from utils.payment_transitions import assert_valid_payment_transition

logger = get_logger(__name__)

GATEWAYS: dict[str, PaymentGateway] = {
    "stripe": StripeGateway(),
    "jazzcash": JazzCashGateway(),
    "easypaisa": EasyPaisaGateway(),
}

_ACTIVE_STATUSES = ("initiated", "processing")
_TERMINAL_STATUSES = ("paid", "failed", "refunded")


class PaymentService:
    """Payment gateway orchestration. Never trusts a client-side "payment succeeded" call — only
    handle_webhook(), fed by a gateway's own signature-verified callback, can move a Payment to
    paid/failed. See utils/payment_transitions.py for the state machine this enforces."""

    @staticmethod
    async def initiate_payment(
        db: AsyncSession, order: Order, gateway_name: str, idempotency_key: Optional[str], user_id: str
    ) -> dict:
        if order.user_id != user_id:
            raise HTTPException(status_code=403, detail="Cannot pay for another user's order")
        if order.status == "cancelled":
            raise HTTPException(status_code=400, detail="Cannot pay for a cancelled order")
        if order.payment_status == "paid":
            raise HTTPException(status_code=400, detail="Order is already paid")

        gateway = GATEWAYS.get(gateway_name)
        if not gateway:
            raise HTTPException(status_code=400, detail=f"Unknown payment gateway: {gateway_name}")
        if not gateway.is_configured():
            raise HTTPException(status_code=503, detail=f"{gateway_name} is not configured on this server")

        # Idempotency: a retried initiate call with the same key re-serves the original attempt's
        # response instead of calling the gateway (and, for Stripe, minting a second
        # PaymentIntent) a second time.
        if idempotency_key:
            existing = (
                await db.execute(select(Payment).where(Payment.idempotency_key == idempotency_key))
            ).scalar_one_or_none()
            if existing:
                if existing.order_id != order.id:
                    raise HTTPException(
                        status_code=409, detail="Idempotency-Key was already used for a different order"
                    )
                return PaymentService._initiate_response(existing)

        # Reuse an already-active attempt on this order rather than starting a second one in
        # parallel (e.g. a double-click before the first request returned).
        active = (
            await db.execute(
                select(Payment).where(Payment.order_id == order.id, Payment.status.in_(_ACTIVE_STATUSES))
            )
        ).scalar_one_or_none()

        payment = active
        if payment is None:
            payment = Payment(
                order_id=order.id,
                gateway=gateway_name,
                status="initiated",
                amount=order.total,
                currency=settings.payment_currency,
                idempotency_key=idempotency_key,
            )
            db.add(payment)
            await db.flush()  # populate payment.id before it's handed to the gateway

        try:
            result = await gateway.initiate(order=order, payment_id=payment.id)
        except Exception as e:
            payment.status = "failed"
            payment.failure_reason = str(e)
            payment.updated_at = datetime.utcnow()
            await log_to_db(
                "PAYMENT_INITIATE_FAILED", __name__, f"gateway call failed for order {order.id}",
                {"order_id": order.id, "payment_id": payment.id, "gateway": gateway_name, "error": str(e)},
            )
            raise HTTPException(status_code=502, detail="Payment gateway request failed")

        payment.raw_response = result
        payment.updated_at = datetime.utcnow()
        order.payment_status = "unpaid"
        order.updated_at = datetime.utcnow()

        await log_to_db(
            "PAYMENT_INITIATED", __name__, f"payment initiated for order {order.id} via {gateway_name}",
            {"order_id": order.id, "payment_id": payment.id, "gateway": gateway_name},
        )

        return PaymentService._initiate_response(payment)

    @staticmethod
    def _initiate_response(payment: Payment) -> dict:
        if payment.status in _TERMINAL_STATUSES:
            return {
                "payment_id": payment.id,
                "gateway": payment.gateway,
                "status": payment.status,
                "message": f"This payment has already been {payment.status}",
            }
        raw = payment.raw_response or {}
        return {
            "payment_id": payment.id,
            "gateway": payment.gateway,
            "status": payment.status,
            "redirect_url": raw.get("redirect_url"),
            "form_fields": raw.get("form_fields"),
            "client_secret": raw.get("client_secret"),
        }

    @staticmethod
    async def handle_webhook(db: AsyncSession, gateway_name: str, headers: dict, body: bytes, params: dict) -> dict:
        gateway = GATEWAYS.get(gateway_name)
        if not gateway:
            raise HTTPException(status_code=404, detail="Unknown payment gateway")
        if not gateway.is_configured():
            raise HTTPException(status_code=503, detail=f"{gateway_name} is not configured")

        try:
            result = gateway.verify_webhook(headers=headers, body=body, params=params)
        except ValueError as e:
            await log_to_db(
                "PAYMENT_WEBHOOK_INVALID_SIGNATURE", __name__, f"{gateway_name} webhook signature rejected",
                {"gateway": gateway_name, "error": str(e)},
            )
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

        # Idempotency: gateways redeliver webhooks aggressively (Stripe especially) — a
        # previously-recorded event is a no-op, not an error, so a retried delivery still gets a
        # clean 200 rather than being treated as a failure worth retrying again.
        existing_event = (
            await db.execute(select(Payment).where(Payment.gateway_event_id == result.event_id))
        ).scalar_one_or_none()
        if existing_event:
            return {"received": True, "duplicate": True}

        payment = await db.get(Payment, result.payment_id) if result.payment_id else None
        if not payment and result.transaction_id:
            payment = (
                await db.execute(select(Payment).where(Payment.gateway_transaction_id == result.transaction_id))
            ).scalar_one_or_none()

        if not payment:
            await log_to_db(
                "PAYMENT_WEBHOOK_UNMATCHED", __name__, f"{gateway_name} webhook matched no payment record",
                {"gateway": gateway_name, "event_id": result.event_id},
            )
            raise HTTPException(status_code=404, detail="No matching payment found")

        # A gateway can legally redeliver after we've already resolved this attempt — treat that
        # as a duplicate rather than re-running (and possibly rejecting) the transition.
        if payment.status in _TERMINAL_STATUSES:
            return {"received": True, "duplicate": True}

        new_status = "paid" if result.success else "failed"
        assert_valid_payment_transition(payment.status, new_status)

        payment.status = new_status
        payment.gateway_event_id = result.event_id
        payment.gateway_transaction_id = result.transaction_id or payment.gateway_transaction_id
        payment.raw_response = result.raw
        payment.updated_at = datetime.utcnow()

        order = await db.get(Order, payment.order_id)
        if order:
            order.payment_status = new_status
            order.updated_at = datetime.utcnow()
            if new_status == "paid" and order.status == "pending":
                assert_valid_transition(order.status, "confirmed")
                order.status = "confirmed"
                db.add(OrderStatusHistory(
                    order_id=order.id, status="confirmed", timestamp=datetime.utcnow(),
                    note=f"Payment confirmed via {gateway_name}",
                ))
                await notify_order_status_change(db, order, "confirmed")

        await log_to_db(
            "PAYMENT_CONFIRMED" if new_status == "paid" else "PAYMENT_FAILED",
            __name__, f"payment {payment.id} for order {payment.order_id} -> {new_status} via {gateway_name}",
            {
                "order_id": payment.order_id, "payment_id": payment.id, "gateway": gateway_name,
                "transaction_id": result.transaction_id,
            },
        )

        return {"received": True, "duplicate": False}

    @staticmethod
    def available_methods() -> dict:
        """Which gateways are actually usable right now — lets the frontend hide payment
        options that would just 503, instead of guessing from static config it can't see."""
        return {
            "cod": True,
            "stripe": GATEWAYS["stripe"].is_configured(),
            "jazzcash": GATEWAYS["jazzcash"].is_configured(),
            "easypaisa": GATEWAYS["easypaisa"].is_configured(),
            "stripe_publishable_key": settings.stripe_publishable_key if GATEWAYS["stripe"].is_configured() else None,
        }

    @staticmethod
    async def resolve_order_id_for_return(db: AsyncSession, gateway_name: str, params: dict) -> Optional[str]:
        """Figure out which order a browser landing back from a redirect-based gateway
        (JazzCash/EasyPaisa) belongs to, purely to know where to send it next — this is a "thank
        you page" lookup, never proof of payment. That's exclusively handle_webhook()'s job."""
        payment_ref = None
        if gateway_name == "jazzcash":
            txn_ref = params.get("pp_TxnRefNo", "")
            payment_ref = txn_ref[1:] if txn_ref.startswith("T") else None
        elif gateway_name == "easypaisa":
            payment_ref = params.get("orderRefNum")

        if not payment_ref or not is_valid_id(payment_ref):
            return None

        payment = await db.get(Payment, payment_ref)
        return payment.order_id if payment else None

    @staticmethod
    async def get_status(db: AsyncSession, order: Order) -> dict:
        latest = (
            await db.execute(
                select(Payment).where(Payment.order_id == order.id).order_by(Payment.created_at.desc())
            )
        ).scalars().first()
        return {
            "order_id": order.id,
            "payment_status": order.payment_status,
            "gateway": latest.gateway if latest else None,
            "gateway_transaction_id": latest.gateway_transaction_id if latest else None,
            "updated_at": order.updated_at,
        }
