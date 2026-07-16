from datetime import datetime, timedelta
from typing import List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.order import Order, OrderItem
from db.product import Product
from db.user import User
from utils.logger import get_logger

logger = get_logger(__name__)

class DashboardService:
    """Dashboard analytics service"""

    @staticmethod
    async def get_dashboard_stats(db: AsyncSession) -> dict:
        """Get key dashboard statistics"""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        total_sales = (await db.execute(
            select(func.coalesce(func.sum(Order.total), 0)).where(Order.status == "delivered")
        )).scalar_one()

        total_orders = (await db.execute(select(func.count()).select_from(Order))).scalar_one()
        total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()

        low_stock = (await db.execute(
            select(func.count()).select_from(Product).where(Product.is_active == True, Product.total_stock <= 10)  # noqa: E712
        )).scalar_one()

        pending_orders = (await db.execute(
            select(func.count()).select_from(Order).where(Order.status == "pending")
        )).scalar_one()

        revenue_today = (await db.execute(
            select(func.coalesce(func.sum(Order.total), 0)).where(
                Order.status == "delivered", Order.created_at >= today
            )
        )).scalar_one()

        orders_today = (await db.execute(
            select(func.count()).select_from(Order).where(Order.created_at >= today)
        )).scalar_one()

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
    async def get_revenue_trend(db: AsyncSession, days: int = 30) -> dict:
        """Get revenue trend for last N days"""
        start_date = datetime.utcnow() - timedelta(days=days)

        day_bucket = func.date_format(Order.created_at, "%Y-%m-%d")
        result = await db.execute(
            select(day_bucket.label("day"), func.sum(Order.total).label("revenue"), func.count().label("orders"))
            .where(Order.status == "delivered", Order.created_at >= start_date)
            .group_by(day_bucket)
            .order_by(day_bucket)
            .limit(days)
        )
        rows = result.all()

        labels = [row.day for row in rows]
        data = [round(row.revenue, 2) for row in rows]

        return {
            "labels": labels,
            "data": data,
        }

    @staticmethod
    async def get_top_products(db: AsyncSession, limit: int = 10) -> List[dict]:
        """Get top selling products. order_items is already a flat child table, so this is one
        query instead of the old $unwind+$group+$sort+$limit pipeline — matches the original's
        behavior of counting items from every order regardless of status (no status filter)."""
        result = await db.execute(
            select(
                OrderItem.product_id,
                func.any_value(OrderItem.name).label("name"),
                func.sum(OrderItem.quantity).label("total_sold"),
                func.sum(OrderItem.quantity * OrderItem.price).label("revenue"),
            )
            .group_by(OrderItem.product_id)
            .order_by(func.sum(OrderItem.quantity).desc())
            .limit(limit)
        )

        return [
            {
                "product_id": row.product_id,
                "name": row.name,
                "total_sold": row.total_sold,
                "revenue": round(row.revenue, 2),
            }
            for row in result.all()
        ]

    @staticmethod
    async def get_low_stock_items(db: AsyncSession, limit: int = 10) -> List[dict]:
        """Get low stock items"""
        from services.product import ProductService
        return await ProductService.get_low_stock_items(db, threshold=10)

    @staticmethod
    async def get_recent_orders(db: AsyncSession, limit: int = 10) -> List[dict]:
        """Get recent orders"""
        from services.order_user import OrderService
        orders, _ = await OrderService.list_orders(db, limit=limit)
        return orders
