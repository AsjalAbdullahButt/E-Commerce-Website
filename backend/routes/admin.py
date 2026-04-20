from fastapi import APIRouter, Depends, Request
from database import products_col, orders_col, users_col
from middleware.auth_middleware import require_admin
from utils.limiter import limiter

router = APIRouter()

@router.get("/stats")
@limiter.limit("30/minute")
async def get_stats(request: Request, _=Depends(require_admin)):
    """Get admin dashboard statistics (admin only)"""
    
    total_products = await products_col.count_documents({"is_active": True})
    total_orders = await orders_col.count_documents({})
    total_users = await users_col.count_documents({"role": "customer"})
    
    # Get order value stats
    orders = await orders_col.find({}).to_list(length=1000)
    total_revenue = sum(o.get("total", 0) for o in orders)
    
    # Get pending orders
    pending_orders = await orders_col.count_documents({"status": "pending"})
    
    # Get top categories
    categories = await products_col.aggregate([
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]).to_list(length=5)
    
    return {
        "total_products": total_products,
        "total_orders": total_orders,
        "total_users": total_users,
        "total_revenue": round(total_revenue, 2),
        "pending_orders": pending_orders,
        "top_categories": [{"category": c["_id"], "count": c["count"]} for c in categories]
    }
