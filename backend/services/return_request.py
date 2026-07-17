from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.order import Order, OrderItem, OrderStatusHistory
from db.return_request import ReturnRequest
from db.user import User
from services.email import EmailService
from services.email_templates import return_request_resolved_email, return_request_submitted_email
from services.order_user import notify_order_status_change
from services.product import InventoryService
from utils.logger import get_logger, log_to_db
from utils.order_transitions import assert_valid_transition

logger = get_logger(__name__)


def _return_request_to_dict(rr: ReturnRequest) -> dict:
    return {
        "id": rr.id, "order_id": rr.order_id, "reason": rr.reason, "status": rr.status,
        "refund_amount": rr.refund_amount, "admin_note": rr.admin_note,
        "resolved_by": rr.resolved_by, "resolved_at": rr.resolved_at, "created_at": rr.created_at,
    }


async def submit_return_request(db: AsyncSession, order: Order, requester_id: Optional[str], reason: str) -> dict:
    """Customer-initiated return/refund request — only while the order is delivered (matches
    the master prompt's "only while order is in an early state" spirit, just at the other end of
    the lifecycle: a return only makes sense once the customer has actually received the item)."""
    if requester_id is not None and order.user_id != requester_id:
        raise HTTPException(status_code=403, detail="Cannot request a return on another user's order")
    if order.status != "delivered":
        raise HTTPException(status_code=400, detail="Only delivered orders can be returned")

    existing = (await db.execute(
        select(ReturnRequest).where(ReturnRequest.order_id == order.id, ReturnRequest.status == "pending")
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="A return request is already pending for this order")

    rr = ReturnRequest(order_id=order.id, reason=reason, status="pending")
    db.add(rr)
    await db.flush()

    subject, html = return_request_submitted_email(order)
    recipient = order.guest_email if order.user_id is None else None
    if order.user_id is not None:
        user = await db.get(User, order.user_id)
        recipient = user.email if user else None
    if recipient:
        await EmailService.send(
            recipient, subject, html,
            event_code="RETURN_REQUEST_SUBMITTED_EMAIL_SENT", meta={"order_id": order.id, "return_request_id": rr.id},
        )

    await log_to_db(
        "RETURN_REQUEST_SUBMITTED", __name__, f"return request {rr.id} submitted for order {order.id}",
        {"order_id": order.id, "return_request_id": rr.id},
    )
    return _return_request_to_dict(rr)


async def resolve_return_request(
    db: AsyncSession, rr: ReturnRequest, action: str, admin_id: str,
    admin_note: Optional[str], refund_amount: Optional[float],
) -> dict:
    if rr.status != "pending":
        raise HTTPException(status_code=400, detail=f"Return request is already {rr.status}")

    order = await db.get(Order, rr.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    approved = action == "approve"
    rr.status = "approved" if approved else "rejected"
    rr.admin_note = admin_note
    rr.resolved_by = admin_id
    rr.resolved_at = datetime.utcnow()
    rr.refund_amount = (refund_amount if refund_amount is not None else order.total) if approved else None

    if approved:
        assert_valid_transition(order.status, "returned")
        order.status = "returned"
        order.updated_at = datetime.utcnow()
        db.add(OrderStatusHistory(
            order_id=order.id, status="returned", timestamp=datetime.utcnow(),
            note=f"Return approved (return request {rr.id})",
        ))
        await notify_order_status_change(db, order, "returned")

        items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
        for it in items_result.scalars().all():
            try:
                restored = await InventoryService.restore_variant_stock(db, it.product_id, it.size, it.color, it.quantity)
                if not restored:
                    await log_to_db("STOCK_RESTORE_FAILED", __name__, "no matching variant to restore stock on return", {"order_id": order.id, "item": it.product_id})
            except Exception:
                await log_to_db("STOCK_RESTORE_FAILED", __name__, "failed to restore stock on return", {"order_id": order.id, "item": it.product_id})

    subject, html = return_request_resolved_email(order, approved, admin_note)
    recipient = None
    if order.user_id is not None:
        user = await db.get(User, order.user_id)
        recipient = user.email if user else None
    else:
        recipient = order.guest_email
    if recipient:
        await EmailService.send(
            recipient, subject, html,
            event_code="RETURN_REQUEST_RESOLVED_EMAIL_SENT",
            meta={"order_id": order.id, "return_request_id": rr.id, "approved": approved},
        )

    await log_to_db(
        "RETURN_REQUEST_RESOLVED", __name__, f"return request {rr.id} {rr.status} by admin {admin_id}",
        {"order_id": order.id, "return_request_id": rr.id, "status": rr.status, "admin_id": admin_id},
    )
    return _return_request_to_dict(rr)
