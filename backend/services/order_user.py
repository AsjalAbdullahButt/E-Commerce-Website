from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.order import Order, OrderItem, OrderNote, OrderStatusHistory
from db.return_request import ReturnRequest
from db.user import User
from services.email import EmailService
from services.email_templates import order_status_update_email
from utils.logger import get_logger
from utils.order_transitions import assert_valid_transition

logger = get_logger(__name__)

# Which order-status transitions are worth emailing the customer about — not every transition in
# utils/order_transitions.py is customer-meaningful ("packed" is an internal warehouse step).
_CUSTOMER_NOTIFIED_STATUSES = {"confirmed", "shipped", "delivered", "cancelled", "returned"}


async def notify_order_status_change(db: AsyncSession, order: Order, new_status: str) -> None:
    """Best-effort order-status email to the customer. Called from every place order.status
    changes (routes/orders.py, routes/rider.py, services/order_user.py, services/payment.py's
    webhook-driven confirmation) — never raises, EmailService.send() already swallows its own
    failures the same way utils/logger.py::log_to_db does."""
    # A couple of call sites (routes/orders.py::update_status, routes/rider.py's status update)
    # pass models.order.OrderStatus enum members straight through from the request body rather
    # than a plain str — equality/DB storage both already work fine since it's a str subclass,
    # but f-string interpolation into the email template below would otherwise render the ugly
    # "OrderStatus.confirmed" instead of "confirmed".
    new_status = new_status.value if hasattr(new_status, "value") else new_status
    if new_status not in _CUSTOMER_NOTIFIED_STATUSES:
        return

    recipient = order.guest_email
    if order.user_id:
        user = await db.get(User, order.user_id)
        recipient = user.email if user else None
    if not recipient:
        return

    subject, html = order_status_update_email(order, new_status)
    await EmailService.send(
        recipient, subject, html,
        event_code="ORDER_STATUS_EMAIL_SENT", meta={"order_id": order.id, "status": new_status},
    )


async def _order_to_dict(db: AsyncSession, order: Order) -> dict:
    items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    items = [
        {"product_id": i.product_id, "name": i.name, "price": i.price, "quantity": i.quantity,
         "size": i.size, "color": i.color, "image": i.image}
        for i in items_result.scalars().all()
    ]

    history_result = await db.execute(
        select(OrderStatusHistory).where(OrderStatusHistory.order_id == order.id).order_by(OrderStatusHistory.timestamp)
    )
    status_history = [
        {"status": h.status, "timestamp": h.timestamp, "note": h.note or ""}
        for h in history_result.scalars().all()
    ]

    latest_return = (await db.execute(
        select(ReturnRequest).where(ReturnRequest.order_id == order.id).order_by(ReturnRequest.created_at.desc())
    )).scalars().first()
    return_request = None
    if latest_return:
        return_request = {
            "id": latest_return.id, "status": latest_return.status, "reason": latest_return.reason,
            "refund_amount": latest_return.refund_amount, "admin_note": latest_return.admin_note,
            "created_at": latest_return.created_at,
        }

    return {
        "id": order.id,
        "user_id": order.user_id,
        "guest_email": order.guest_email,
        "items": items,
        "shipping_address": {
            "full_name": order.full_name, "phone": order.phone, "address": order.address,
            "city": order.city, "postal_code": order.postal_code,
        },
        "payment_method": order.payment_method,
        "payment_reference": order.payment_reference,
        "payment_status": order.payment_status,
        "promo_code": order.promo_code,
        "subtotal": order.subtotal,
        "discount": order.discount,
        "tax": order.tax,
        "delivery_fee": order.delivery_fee,
        "total": order.total,
        "status": order.status,
        "rider_id": order.rider_id,
        "proof_of_delivery_url": order.proof_of_delivery_url,
        "status_history": status_history,
        "return_request": return_request,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }


class OrderService:
    """Order management service.

    Operates on the canonical order shape written by the real checkout flow
    (routes/orders.py::place_order): status/status_history/total — NOT the
    legacy timeline/total_price/final_price shape. See NOTES_schema_audit.md §2.
    """

    @staticmethod
    async def get_order(db: AsyncSession, order_id: str) -> dict:
        """Get order by ID"""
        order = await db.get(Order, order_id)

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )

        return await _order_to_dict(db, order)

    @staticmethod
    async def update_order_status(
        db: AsyncSession,
        order_id: str,
        new_status: str,
        note: Optional[str],
        admin_id: str,
    ) -> dict:
        """Update order status with validation"""
        order = await db.get(Order, order_id)
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        current_status = order.status

        assert_valid_transition(current_status, new_status)

        order.status = new_status
        order.updated_at = datetime.now(timezone.utc)
        db.add(OrderStatusHistory(
            order_id=order_id, status=new_status, timestamp=datetime.now(timezone.utc), note=note or "",
        ))
        await notify_order_status_change(db, order, new_status)

        # Log audit
        from services.admin_auth import AdminAuditService
        await AdminAuditService.log_action(
            admin_id=admin_id,
            admin_name="System",
            action="update_order_status",
            entity_type="order",
            entity_id=order_id,
            changes={"status": {"old": current_status, "new": new_status}},
            ip_address="0.0.0.0"
        )

        logger.info(f"Order {order_id} status updated: {current_status} -> {new_status}")
        return await OrderService.get_order(db, order_id)

    @staticmethod
    async def list_orders(
        db: AsyncSession,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> tuple:
        """List orders with filtering"""
        query = select(Order)
        count_query = select(func.count()).select_from(Order)

        if status:
            query = query.where(Order.status == status)
            count_query = count_query.where(Order.status == status)
        if user_id:
            query = query.where(Order.user_id == user_id)
            count_query = count_query.where(Order.user_id == user_id)

        query = query.order_by(Order.created_at.desc()).offset(skip).limit(limit)

        result = await db.execute(query)
        orders = result.scalars().all()
        out = [await _order_to_dict(db, o) for o in orders]

        total = (await db.execute(count_query)).scalar_one()
        return out, total

    @staticmethod
    async def add_order_note(db: AsyncSession, order_id: str, note: str, admin_id: str) -> dict:
        """Add note to order"""
        order = await db.get(Order, order_id)
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        db.add(OrderNote(order_id=order_id, text=note, added_by=admin_id, timestamp=datetime.now(timezone.utc)))
        order.updated_at = datetime.now(timezone.utc)

        logger.info(f"Note added to order {order_id} by admin {admin_id}")
        return await OrderService.get_order(db, order_id)


class UserService:
    """User management service for admin"""

    @staticmethod
    async def get_user(db: AsyncSession, user_id: str) -> dict:
        """Get user by ID"""
        user = await db.get(User, user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        data = {c.name: getattr(user, c.name) for c in User.__table__.columns}
        data.pop("password", None)
        return data

    @staticmethod
    async def list_users(
        db: AsyncSession,
        is_banned: Optional[bool] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> tuple:
        """List users"""
        query = select(User)
        count_query = select(func.count()).select_from(User)

        if is_banned is not None:
            query = query.where(User.is_banned == is_banned)
            count_query = count_query.where(User.is_banned == is_banned)

        query = query.order_by(User.created_at.desc()).offset(skip).limit(limit)

        result = await db.execute(query)
        users = result.scalars().all()
        out = []
        for u in users:
            data = {c.name: getattr(u, c.name) for c in User.__table__.columns}
            data.pop("password", None)
            out.append(data)

        total = (await db.execute(count_query)).scalar_one()
        return out, total

    @staticmethod
    async def ban_user(db: AsyncSession, user_id: str, reason: str, admin_id: str) -> dict:
        """Ban user account"""
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        user.is_banned = True
        user.ban_reason = reason
        user.banned_by = admin_id
        user.banned_at = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc)

        # Log audit
        from services.admin_auth import AdminAuditService
        await AdminAuditService.log_action(
            admin_id=admin_id,
            admin_name="System",
            action="ban_user",
            entity_type="user",
            entity_id=user_id,
            changes={"is_banned": {"old": False, "new": True}, "ban_reason": {"old": None, "new": reason}},
            ip_address="0.0.0.0"
        )

        logger.info(f"User {user_id} banned by admin {admin_id}: {reason}")
        return await UserService.get_user(db, user_id)

    @staticmethod
    async def unban_user(db: AsyncSession, user_id: str, admin_id: str) -> dict:
        """Unban user account"""
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        user.is_banned = False
        user.ban_reason = None
        user.banned_by = None
        user.banned_at = None
        user.updated_at = datetime.now(timezone.utc)

        # Log audit
        from services.admin_auth import AdminAuditService
        await AdminAuditService.log_action(
            admin_id=admin_id,
            admin_name="System",
            action="unban_user",
            entity_type="user",
            entity_id=user_id,
            changes={"is_banned": {"old": True, "new": False}},
            ip_address="0.0.0.0"
        )

        logger.info(f"User {user_id} unbanned by admin {admin_id}")
        return await UserService.get_user(db, user_id)

    @staticmethod
    async def get_user_order_history(db: AsyncSession, user_id: str, limit: int = 20) -> List[dict]:
        """Get user's order history"""
        result = await db.execute(
            select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()).limit(limit)
        )
        orders = result.scalars().all()
        return [await _order_to_dict(db, o) for o in orders]
