from fastapi import HTTPException, status
from database import riders_col, orders_col
from bson import ObjectId
from datetime import datetime
from typing import Optional
from utils.helpers import hash_password
from utils.logger import get_logger

logger = get_logger(__name__)

ACTIVE_ORDER_STATUSES = ["pending", "confirmed", "packed", "shipped"]


class RiderService:
    """Admin-facing rider management. Reads/writes riders_col in the same field shape
    routes/auth.py's unified login and routes/rider.py's self-service endpoints already expect
    (`password`, not `password_hash`; `status`: available/busy/offline)."""

    @staticmethod
    def _serialize(rider: dict) -> dict:
        rider = dict(rider)
        rider["id"] = str(rider.pop("_id"))
        rider.pop("password", None)
        return rider

    @staticmethod
    async def create_rider(name: str, email: str, password: str, phone: str, admin_id: str) -> dict:
        existing = await riders_col.find_one({"email": email})
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Rider with this email already exists")

        doc = {
            "name": name,
            "email": email,
            "password": hash_password(password),
            "phone": phone,
            "is_active": True,
            "status": "offline",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        result = await riders_col.insert_one(doc)

        from services.admin_auth import AdminAuditService
        await AdminAuditService.log_action(
            admin_id=admin_id, admin_name="System", action="create_rider",
            entity_type="rider", entity_id=str(result.inserted_id),
            changes={"email": {"old": None, "new": email}}, ip_address="0.0.0.0",
        )

        logger.info(f"Rider created: {email} by admin {admin_id}")
        rider = await riders_col.find_one({"_id": result.inserted_id})
        return RiderService._serialize(rider)

    @staticmethod
    async def list_riders(is_active: Optional[bool] = None) -> list[dict]:
        query: dict = {}
        if is_active is not None:
            query["is_active"] = is_active
        riders = await riders_col.find(query).sort("created_at", -1).to_list(length=500)
        return [RiderService._serialize(r) for r in riders]

    @staticmethod
    async def get_rider(rider_id: str) -> dict:
        try:
            oid = ObjectId(rider_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid rider ID")
        rider = await riders_col.find_one({"_id": oid})
        if not rider:
            raise HTTPException(status_code=404, detail="Rider not found")
        return rider

    @staticmethod
    async def set_active(rider_id: str, is_active: bool, admin_id: str) -> dict:
        rider = await RiderService.get_rider(rider_id)
        await riders_col.update_one(
            {"_id": rider["_id"]},
            {"$set": {"is_active": is_active, "updated_at": datetime.utcnow()}},
        )

        from services.admin_auth import AdminAuditService
        await AdminAuditService.log_action(
            admin_id=admin_id, admin_name="System",
            action="activate_rider" if is_active else "deactivate_rider",
            entity_type="rider", entity_id=rider_id,
            changes={"is_active": {"old": rider.get("is_active", True), "new": is_active}},
            ip_address="0.0.0.0",
        )

        logger.info(f"Rider {rider_id} {'activated' if is_active else 'deactivated'} by admin {admin_id}")
        updated = await riders_col.find_one({"_id": rider["_id"]})
        return RiderService._serialize(updated)

    @staticmethod
    async def get_active_order_count(rider_id: str) -> int:
        await RiderService.get_rider(rider_id)  # 404 if rider doesn't exist
        return await orders_col.count_documents({
            "rider_id": rider_id,
            "status": {"$in": ACTIVE_ORDER_STATUSES},
        })

    @staticmethod
    async def is_available_for_assignment(rider_id: str) -> bool:
        """True if the rider exists, is active, and is not marked busy/offline."""
        try:
            rider = await RiderService.get_rider(rider_id)
        except HTTPException:
            return False
        return bool(rider.get("is_active", True)) and rider.get("status") != "offline"
