from fastapi import HTTPException, status
from database import products_col, inventory_history_col, audit_logs_col, admin_users_col
from models.admin import product_document, inventory_history_document, inventory_log_entry
from bson import ObjectId
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger("product_service")

class ProductService:
    """Product management service"""

    @staticmethod
    async def create_product(
        name: str,
        description: str,
        category: str,
        price: float,
        discount_percentage: float,
        variants: List[dict],
        tags: List[str],
        images: List[str],
        admin_id: str,
    ) -> str:
        """Create new product"""
        doc = product_document(
            name=name,
            description=description,
            category=category,
            price=price,
            discount_percentage=discount_percentage,
            variants=variants,
            tags=tags,
            images=images,
        )
        doc["created_by"] = admin_id
        
        result = await products_col.insert_one(doc)
        product_id = str(result.inserted_id)
        
        # Create inventory history document
        inv_history = inventory_history_document(product_id)
        inv_history["initial_variants"] = variants
        await inventory_history_col.insert_one(inv_history)
        
        logger.info(f"Product created: {name} ({product_id}) by admin {admin_id}")
        return product_id

    @staticmethod
    async def get_product(product_id: str) -> dict:
        """Get product by ID"""
        product = await products_col.find_one(
            {"_id": ObjectId(product_id), "is_deleted": False}
        )
        
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        
        product["id"] = str(product["_id"])
        del product["_id"]
        return product

    @staticmethod
    async def update_product(
        product_id: str,
        updates: dict,
        admin_id: str,
    ) -> dict:
        """Update product"""
        product = await ProductService.get_product(product_id)
        
        # Recalculate total stock if variants changed
        if "variants" in updates:
            updates["total_stock"] = sum(v.get('stock', 0) for v in updates["variants"])
            updates["discount_price"] = updates.get("price", product["price"]) * (1 - updates.get("discount_percentage", product["discount_percentage"]) / 100)
        
        updates["updated_at"] = datetime.utcnow()
        
        await products_col.update_one(
            {"_id": ObjectId(product_id)},
            {"$set": updates}
        )
        
        # Log audit
        from services.admin_auth import AdminAuditService
        await AdminAuditService.log_action(
            admin_id=admin_id,
            admin_name="System",
            action="update_product",
            entity_type="product",
            entity_id=product_id,
            changes={k: {"old": product.get(k), "new": v} for k, v in updates.items() if k != "updated_at"},
            ip_address="0.0.0.0"
        )
        
        logger.info(f"Product updated: {product_id} by admin {admin_id}")
        return await ProductService.get_product(product_id)

    @staticmethod
    async def delete_product(product_id: str, admin_id: str) -> bool:
        """Soft delete product"""
        product = await ProductService.get_product(product_id)
        
        await products_col.update_one(
            {"_id": ObjectId(product_id)},
            {
                "$set": {
                    "is_deleted": True,
                    "is_active": False,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # Log audit
        from services.admin_auth import AdminAuditService
        await AdminAuditService.log_action(
            admin_id=admin_id,
            admin_name="System",
            action="delete_product",
            entity_type="product",
            entity_id=product_id,
            changes={"is_deleted": {"old": False, "new": True}},
            ip_address="0.0.0.0"
        )
        
        logger.info(f"Product soft deleted: {product_id} by admin {admin_id}")
        return True

    @staticmethod
    async def list_products(
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> tuple:
        """List products with filtering"""
        query = {"is_deleted": False}
        
        if category:
            query["category"] = category
        if is_active is not None:
            query["is_active"] = is_active
        
        cursor = products_col.find(query).sort("created_at", -1).skip(skip).limit(limit)
        products = await cursor.to_list(length=limit)
        
        # Convert ObjectId
        for p in products:
            p["id"] = str(p["_id"])
            del p["_id"]
        
        total = await products_col.count_documents(query)
        return products, total

    @staticmethod
    async def get_low_stock_items(threshold: int = 10) -> List[dict]:
        """Get products with low stock"""
        products = await products_col.find(
            {
                "is_deleted": False,
                "total_stock": {"$lte": threshold}
            }
        ).to_list(length=100)
        
        for p in products:
            p["id"] = str(p["_id"])
            del p["_id"]
        
        return products


class InventoryService:
    """Inventory management service"""

    @staticmethod
    async def adjust_stock(
        product_id: str,
        variant_sku: str,
        quantity_change: int,
        reason: str,
        admin_id: str,
    ) -> bool:
        """Adjust stock for a variant"""
        product = await ProductService.get_product(product_id)
        
        # Find variant
        variant = next(
            (v for v in product.get("variants", []) if v["sku"] == variant_sku),
            None
        )
        
        if not variant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Variant not found"
            )
        
        new_stock = variant["stock"] + quantity_change
        
        if new_stock < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reduce stock below 0"
            )
        
        # Update variant stock
        updated_variants = product["variants"]
        for v in updated_variants:
            if v["sku"] == variant_sku:
                v["stock"] = new_stock
        
        total_stock = sum(v.get("stock", 0) for v in updated_variants)
        
        await products_col.update_one(
            {"_id": ObjectId(product_id)},
            {
                "$set": {
                    "variants": updated_variants,
                    "total_stock": total_stock,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # Log to inventory history
        log_entry = inventory_log_entry(
            product_id=product_id,
            variant_sku=variant_sku,
            quantity_changed=quantity_change,
            reason=reason,
            admin_id=admin_id,
        )
        
        await inventory_history_col.update_one(
            {"product_id": product_id},
            {"$push": {"logs": log_entry}, "$set": {"updated_at": datetime.utcnow()}},
            upsert=True
        )
        
        logger.info(f"Stock adjusted for {variant_sku}: {quantity_change} ({reason})")
        return True

    @staticmethod
    async def get_inventory_history(product_id: str, limit: int = 100) -> dict:
        """Get inventory history for product"""
        history = await inventory_history_col.find_one({"product_id": product_id})
        
        if not history:
            return {"product_id": product_id, "logs": []}
        
        # Get last N logs
        logs = history.get("logs", [])[-limit:]
        
        return {
            "product_id": product_id,
            "logs": logs,
            "total_logs": len(history.get("logs", [])),
        }
