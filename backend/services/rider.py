from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.order import Order
from db.rider import Rider
from utils.helpers import hash_password
from utils.ids import is_valid_id
from utils.logger import get_logger

logger = get_logger(__name__)

ACTIVE_ORDER_STATUSES = ["pending", "confirmed", "packed", "shipped"]


def _serialize(rider: Rider) -> dict:
    data = {c.name: getattr(rider, c.name) for c in Rider.__table__.columns}
    data.pop("password", None)
    return data


class RiderService:
    """Admin-facing rider management. Reads/writes the `riders` table in the same field shape
    routes/auth.py's unified login and routes/rider.py's self-service endpoints already expect
    (`password`, not `password_hash`; `status`: available/busy/offline)."""

    @staticmethod
    async def create_rider(db: AsyncSession, name: str, email: str, password: str, phone: str, admin_id: str) -> dict:
        existing = await db.execute(select(Rider).where(Rider.email == email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Rider with this email already exists")

        rider = Rider(name=name, email=email, password=hash_password(password), phone=phone, is_active=True, status="offline")
        db.add(rider)
        await db.flush()

        from services.admin_auth import AdminAuditService
        await AdminAuditService.log_action(
            admin_id=admin_id, admin_name="System", action="create_rider",
            entity_type="rider", entity_id=rider.id,
            changes={"email": {"old": None, "new": email}}, ip_address="0.0.0.0",
        )

        logger.info(f"Rider created: {email} by admin {admin_id}")
        return _serialize(rider)

    @staticmethod
    async def list_riders(db: AsyncSession, is_active: Optional[bool] = None) -> list[dict]:
        query = select(Rider)
        if is_active is not None:
            query = query.where(Rider.is_active == is_active)
        query = query.order_by(Rider.created_at.desc()).limit(500)
        result = await db.execute(query)
        return [_serialize(r) for r in result.scalars().all()]

    @staticmethod
    async def get_rider(db: AsyncSession, rider_id: str) -> Rider:
        if not is_valid_id(rider_id):
            raise HTTPException(status_code=400, detail="Invalid rider ID")
        rider = await db.get(Rider, rider_id)
        if not rider:
            raise HTTPException(status_code=404, detail="Rider not found")
        return rider

    @staticmethod
    async def set_active(db: AsyncSession, rider_id: str, is_active: bool, admin_id: str) -> dict:
        rider = await RiderService.get_rider(db, rider_id)
        old_active = rider.is_active
        rider.is_active = is_active
        rider.updated_at = datetime.utcnow()

        from services.admin_auth import AdminAuditService
        await AdminAuditService.log_action(
            admin_id=admin_id, admin_name="System",
            action="activate_rider" if is_active else "deactivate_rider",
            entity_type="rider", entity_id=rider_id,
            changes={"is_active": {"old": old_active, "new": is_active}},
            ip_address="0.0.0.0",
        )

        logger.info(f"Rider {rider_id} {'activated' if is_active else 'deactivated'} by admin {admin_id}")
        return _serialize(rider)

    @staticmethod
    async def get_active_order_count(db: AsyncSession, rider_id: str) -> int:
        await RiderService.get_rider(db, rider_id)  # 404 if rider doesn't exist
        result = await db.execute(
            select(func.count()).select_from(Order).where(
                Order.rider_id == rider_id, Order.status.in_(ACTIVE_ORDER_STATUSES)
            )
        )
        return result.scalar_one()

    @staticmethod
    async def is_available_for_assignment(db: AsyncSession, rider_id: str) -> bool:
        """True if the rider exists, is active, and is not marked busy/offline."""
        try:
            rider = await RiderService.get_rider(db, rider_id)
        except HTTPException:
            return False
        return bool(rider.is_active) and rider.status != "offline"
