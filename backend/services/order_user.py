from fastapi import HTTPException, status
from database import orders_col, users_col, products_col, admin_users_col
from bson import ObjectId
from datetime import datetime
from typing import Optional, List
import logging

logger = logging.getLogger("order_service")

class OrderService:
    """Order management service"""

    @staticmethod
    async def get_order(order_id: str) -> dict:
        """Get order by ID"""
        order = await orders_col.find_one({"_id": ObjectId(order_id), "is_deleted": False})
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        order["id"] = str(order["_id"])
        del order["_id"]
        return order

    @staticmethod
    async def update_order_status(
        order_id: str,
        new_status: str,
        note: Optional[str],
        admin_id: str,
    ) -> dict:
        """Update order status with validation"""
        order = await OrderService.get_order(order_id)
        current_status = order["status"]
        
        # Validate status transition
        valid_transitions = {
            "pending": ["confirmed", "cancelled"],
            "confirmed": ["packed", "cancelled"],
            "packed": ["shipped"],
            "shipped": ["delivered"],
            "delivered": ["returned"],
            "cancelled": [],
            "returned": [],
        }
        
        if new_status not in valid_transitions.get(current_status, []):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot transition from {current_status} to {new_status}"
            )
        
        # Add to timeline
        timeline_entry = {
            "status": new_status,
            "timestamp": datetime.utcnow(),
            "note": note,
            "updated_by": admin_id,
        }
        
        await orders_col.update_one(
            {"_id": ObjectId(order_id)},
            {
                "$set": {"status": new_status, "updated_at": datetime.utcnow()},
                "$push": {"timeline": timeline_entry}
            }
        )
        
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
        return await OrderService.get_order(order_id)

    @staticmethod
    async def list_orders(
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> tuple:
        """List orders with filtering"""
        query = {"is_deleted": False}
        
        if status:
            query["status"] = status
        if user_id:
            query["user_id"] = user_id
        
        cursor = orders_col.find(query).sort("created_at", -1).skip(skip).limit(limit)
        orders = await cursor.to_list(length=limit)
        
        for o in orders:
            o["id"] = str(o["_id"])
            del o["_id"]
        
        total = await orders_col.count_documents(query)
        return orders, total

    @staticmethod
    async def get_pending_orders() -> List[dict]:
        """Get all pending orders"""
        orders, _ = await OrderService.list_orders(status="pending", limit=1000)
        return orders

    @staticmethod
    async def add_order_note(order_id: str, note: str, admin_id: str) -> dict:
        """Add note to order"""
        order = await OrderService.get_order(order_id)
        
        await orders_col.update_one(
            {"_id": ObjectId(order_id)},
            {
                "$push": {"notes": {"text": note, "added_by": admin_id, "timestamp": datetime.utcnow()}},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        logger.info(f"Note added to order {order_id} by admin {admin_id}")
        return await OrderService.get_order(order_id)


class UserService:
    """User management service for admin"""

    @staticmethod
    async def get_user(user_id: str) -> dict:
        """Get user by ID"""
        user = await users_col.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user["id"] = str(user["_id"])
        del user["_id"]
        user.pop("password_hash", None)  # Remove password
        
        return user

    @staticmethod
    async def list_users(
        is_banned: Optional[bool] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> tuple:
        """List users"""
        query = {}
        
        if is_banned is not None:
            query["is_banned"] = is_banned
        
        cursor = users_col.find(query).sort("created_at", -1).skip(skip).limit(limit)
        users = await cursor.to_list(length=limit)
        
        for u in users:
            u["id"] = str(u["_id"])
            del u["_id"]
            u.pop("password_hash", None)
        
        total = await users_col.count_documents(query)
        return users, total

    @staticmethod
    async def ban_user(user_id: str, reason: str, admin_id: str) -> dict:
        """Ban user account"""
        user = await UserService.get_user(user_id)
        
        await users_col.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "is_banned": True,
                    "ban_reason": reason,
                    "banned_by": admin_id,
                    "banned_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            }
        )
        
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
        return await UserService.get_user(user_id)

    @staticmethod
    async def unban_user(user_id: str, admin_id: str) -> dict:
        """Unban user account"""
        user = await UserService.get_user(user_id)
        
        await users_col.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "is_banned": False,
                    "ban_reason": None,
                    "banned_by": None,
                    "banned_at": None,
                    "updated_at": datetime.utcnow(),
                }
            }
        )
        
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
        return await UserService.get_user(user_id)

    @staticmethod
    async def get_user_order_history(user_id: str, limit: int = 20) -> List[dict]:
        """Get user's order history"""
        orders = await orders_col.find(
            {"user_id": user_id, "is_deleted": False}
        ).sort("created_at", -1).limit(limit).to_list(length=limit)
        
        for o in orders:
            o["id"] = str(o["_id"])
            del o["_id"]
        
        return orders
