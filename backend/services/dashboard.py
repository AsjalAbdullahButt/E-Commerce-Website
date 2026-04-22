from database import orders_col, products_col, users_col
from datetime import datetime, timedelta
from typing import List
import logging

logger = logging.getLogger("dashboard_service")

class DashboardService:
    """Dashboard analytics service"""

    @staticmethod
    async def get_dashboard_stats() -> dict:
        """Get key dashboard statistics"""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Total sales (sum of final_price for delivered orders)
        total_sales_result = await orders_col.aggregate([
            {"$match": {"status": "delivered"}},
            {"$group": {"_id": None, "total": {"$sum": "$final_price"}}}
        ]).to_list(length=1)
        total_sales = total_sales_result[0]["total"] if total_sales_result else 0
        
        # Total orders
        total_orders = await orders_col.count_documents({"is_deleted": False})
        
        # Total users
        total_users = await users_col.count_documents({})
        
        # Low stock items
        low_stock = await products_col.count_documents({
            "is_deleted": False,
            "total_stock": {"$lte": 10}
        })
        
        # Pending orders
        pending_orders = await orders_col.count_documents({"status": "pending"})
        
        # Revenue today
        today_result = await orders_col.aggregate([
            {
                "$match": {
                    "status": "delivered",
                    "created_at": {"$gte": today}
                }
            },
            {"$group": {"_id": None, "total": {"$sum": "$final_price"}}}
        ]).to_list(length=1)
        revenue_today = today_result[0]["total"] if today_result else 0
        
        # Orders today
        orders_today = await orders_col.count_documents({
            "created_at": {"$gte": today}
        })
        
        return {
            "total_sales": round(total_sales, 2),
            "total_orders": total_orders,
            "total_users": total_users,
            "low_stock_items": low_stock,
            "pending_orders": pending_orders,
            "revenue_today": round(revenue_today, 2),
            "orders_today": orders_today,
        }

    @staticmethod
    async def get_revenue_trend(days: int = 30) -> dict:
        """Get revenue trend for last N days"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        result = await orders_col.aggregate([
            {
                "$match": {
                    "status": "delivered",
                    "created_at": {"$gte": start_date}
                }
            },
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$created_at"
                        }
                    },
                    "revenue": {"$sum": "$final_price"},
                    "orders": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}}
        ]).to_list(length=days)
        
        labels = [item["_id"] for item in result]
        data = [round(item["revenue"], 2) for item in result]
        
        return {
            "labels": labels,
            "data": data,
        }

    @staticmethod
    async def get_top_products(limit: int = 10) -> List[dict]:
        """Get top selling products"""
        result = await orders_col.aggregate([
            {"$unwind": "$items"},
            {
                "$group": {
                    "_id": "$items.product_id",
                    "name": {"$first": "$items.product_name"},
                    "total_sold": {"$sum": "$items.quantity"},
                    "revenue": {"$sum": {"$multiply": ["$items.quantity", "$items.price"]}}
                }
            },
            {"$sort": {"total_sold": -1}},
            {"$limit": limit}
        ]).to_list(length=limit)
        
        products = []
        for item in result:
            products.append({
                "product_id": str(item["_id"]),
                "name": item["name"],
                "total_sold": item["total_sold"],
                "revenue": round(item["revenue"], 2),
            })
        
        return products

    @staticmethod
    async def get_low_stock_items(limit: int = 10) -> List[dict]:
        """Get low stock items"""
        from services.product import ProductService
        return await ProductService.get_low_stock_items(threshold=10)

    @staticmethod
    async def get_recent_orders(limit: int = 10) -> List[dict]:
        """Get recent orders"""
        from services.order_user import OrderService
        orders, _ = await OrderService.list_orders(limit=limit)
        return orders
