from fastapi import HTTPException, status
from database import promos_col, orders_col
from bson import ObjectId
from datetime import datetime
from typing import Optional
from utils.logger import get_logger

logger = get_logger(__name__)

class DiscountService:
    """Discount and coupon management service backed by promos_col."""

    @staticmethod
    async def create_discount(
        code: str,
        description: str,
        discount_type: str,
        discount_value: float,
        max_usage: int,
        min_order_value: float,
        expiry_date: datetime,
        admin_id: str,
    ) -> str:
        """Create new discount/coupon"""
        # Check if code already exists
        existing = await promos_col.find_one({"code": code.upper()})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Discount code already exists"
            )

        doc = {
            "code": code.upper(),
            "description": description,
            "discount_type": discount_type,
            "discount_value": discount_value,
            "max_uses": max_usage,
            "uses": 0,
            "min_order": min_order_value,
            "expires_at": expiry_date,
            "created_by": admin_id,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        result = await promos_col.insert_one(doc)
        
        # Log audit
        from services.admin_auth import AdminAuditService
        await AdminAuditService.log_action(
            admin_id=admin_id,
            admin_name="System",
            action="create_discount",
            entity_type="discount",
            entity_id=str(result.inserted_id),
            changes={"code": {"old": None, "new": code}},
            ip_address="0.0.0.0"
        )
        
        logger.info(f"Discount created: {code} by admin {admin_id}")
        return str(result.inserted_id)

    @staticmethod
    async def get_discount(discount_id: str) -> dict:
        """Get discount by ID"""
        discount = await promos_col.find_one({"_id": ObjectId(discount_id)})
        
        if not discount:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Discount not found"
            )
        
        discount["id"] = str(discount["_id"])
        del discount["_id"]
        return discount

    @staticmethod
    async def get_discount_by_code(code: str) -> dict:
        """Get discount by code"""
        discount = await promos_col.find_one({"code": code.upper(), "is_active": True})
        
        if not discount:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Discount code not found or expired"
            )
        
        # Check expiry
        expires_at = discount.get("expires_at")
        if isinstance(expires_at, str):
            try:
                expires_at = datetime.fromisoformat(expires_at)
            except Exception:
                expires_at = None
        if expires_at and expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Discount code has expired"
            )
        
        # Check usage
        if discount.get("uses", 0) >= discount.get("max_uses", 0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Discount code has reached maximum usage"
            )
        
        discount["id"] = str(discount["_id"])
        del discount["_id"]
        return discount

    @staticmethod
    async def update_discount(
        discount_id: str,
        updates: dict,
        admin_id: str,
    ) -> dict:
        """Update discount"""
        discount = await DiscountService.get_discount(discount_id)
        
        updates["updated_at"] = datetime.utcnow()
        
        await promos_col.update_one(
            {"_id": ObjectId(discount_id)},
            {"$set": updates}
        )
        
        # Log audit
        from services.admin_auth import AdminAuditService
        await AdminAuditService.log_action(
            admin_id=admin_id,
            admin_name="System",
            action="update_discount",
            entity_type="discount",
            entity_id=discount_id,
            changes={k: {"old": discount.get(k), "new": v} for k, v in updates.items() if k != "updated_at"},
            ip_address="0.0.0.0"
        )
        
        logger.info(f"Discount updated: {discount_id}")
        return await DiscountService.get_discount(discount_id)

    @staticmethod
    async def deactivate_discount(discount_id: str, admin_id: str) -> dict:
        """Deactivate discount"""
        return await DiscountService.update_discount(
            discount_id=discount_id,
            updates={"is_active": False},
            admin_id=admin_id
        )

    @staticmethod
    async def list_discounts(
        is_active: Optional[bool] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> tuple:
        """List discounts"""
        query = {}
        
        if is_active is not None:
            query["is_active"] = is_active
        
        cursor = promos_col.find(query).sort("created_at", -1).skip(skip).limit(limit)
        discounts = await cursor.to_list(length=limit)
        
        for d in discounts:
            d["id"] = str(d["_id"])
            del d["_id"]
        
        total = await promos_col.count_documents(query)
        return discounts, total

    @staticmethod
    async def apply_discount_to_order(order_id: str, discount_code: str) -> tuple:
        """Apply discount to order and calculate discount amount"""
        # Get order
        from services.order_user import OrderService
        order = await OrderService.get_order(order_id)
        
        # Get discount
        discount = await DiscountService.get_discount_by_code(discount_code)
        
        # Check minimum order value
        order_total = float(order.get("total_price", order.get("total", 0)) or 0)
        if order_total < float(discount.get("min_order", 0) or 0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order must be at least {discount.get('min_order', 0)} to use this discount"
            )
        
        # Calculate discount amount
        if discount["discount_type"] == "percentage":
            discount_amount = order_total * (discount["discount_value"] / 100)
        else:  # fixed
            discount_amount = discount["discount_value"]
        
        final_price = order_total - discount_amount
        
        # Update order
        await orders_col.update_one(
            {"_id": ObjectId(order_id)},
            {
                "$set": {
                    "discount_applied": discount_amount,
                    "final_price": final_price,
                    "discount_code_used": discount_code,
                    "updated_at": datetime.utcnow(),
                }
            }
        )
        
        # Increment discount usage
        await promos_col.update_one(
            {"_id": ObjectId(discount["id"])},
            {"$inc": {"uses": 1}, "$set": {"updated_at": datetime.utcnow()}}
        )
        
        logger.info(f"Discount {discount_code} applied to order {order_id}")
        return discount_amount, final_price
