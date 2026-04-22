from fastapi import HTTPException, status
from database import discounts_col, orders_col
from models.admin import discount_document
from bson import ObjectId
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger("discount_service")

class DiscountService:
    """Discount and coupon management service"""

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
        existing = await discounts_col.find_one({"code": code.upper()})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Discount code already exists"
            )
        
        doc = discount_document(
            code=code,
            description=description,
            discount_type=discount_type,
            discount_value=discount_value,
            max_usage=max_usage,
            min_order_value=min_order_value,
            expiry_date=expiry_date,
            created_by=admin_id,
        )
        
        result = await discounts_col.insert_one(doc)
        
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
        discount = await discounts_col.find_one({"_id": ObjectId(discount_id)})
        
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
        discount = await discounts_col.find_one({"code": code.upper(), "is_active": True})
        
        if not discount:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Discount code not found or expired"
            )
        
        # Check expiry
        if discount["expiry_date"] < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Discount code has expired"
            )
        
        # Check usage
        if discount["current_usage"] >= discount["max_usage"]:
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
        
        await discounts_col.update_one(
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
        
        cursor = discounts_col.find(query).sort("created_at", -1).skip(skip).limit(limit)
        discounts = await cursor.to_list(length=limit)
        
        for d in discounts:
            d["id"] = str(d["_id"])
            del d["_id"]
        
        total = await discounts_col.count_documents(query)
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
        if order["total_price"] < discount["min_order_value"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order must be at least {discount['min_order_value']} to use this discount"
            )
        
        # Calculate discount amount
        if discount["discount_type"] == "percentage":
            discount_amount = order["total_price"] * (discount["discount_value"] / 100)
        else:  # fixed
            discount_amount = discount["discount_value"]
        
        final_price = order["total_price"] - discount_amount
        
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
        await discounts_col.update_one(
            {"_id": ObjectId(discount["id"])},
            {"$inc": {"current_usage": 1}}
        )
        
        logger.info(f"Discount {discount_code} applied to order {order_id}")
        return discount_amount, final_price
