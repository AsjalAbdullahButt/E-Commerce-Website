from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from middleware.admin_auth import verify_admin_token, check_permission
from schemas.admin import *
from services.admin_auth import AdminAuthService, AdminAuditService
from services.product import ProductService, InventoryService
from services.order_user import OrderService, UserService
from services.discount import DiscountService
from services.dashboard import DashboardService
from services.rider import RiderService
from schemas.rider import RiderCreate
from typing import Optional
from utils.logger import get_logger, log_to_db
from utils.cache import cache_get, cache_set, cache_clear_prefix, cache_delete
from utils.order_transitions import assert_valid_transition
from database import products_col, orders_col, users_col
from bson import ObjectId
from datetime import datetime
from config import settings
from utils.limiter import limiter
from utils.csrf import generate_csrf_token, set_csrf_cookie, verify_csrf

logger = get_logger(__name__)

# Router intentionally has no internal prefix — main.py mounts it with prefix="/admin"
router = APIRouter(tags=["Admin"])


# Simple stats endpoint (kept from legacy admin module) mounted at /admin/stats
@router.get("/stats")
@limiter.limit("30/minute")
async def legacy_stats(request: Request, _=Depends(verify_admin_token)):
    """Get admin dashboard statistics (admin only)"""
    try:
        total_products = await products_col.count_documents({"is_active": True})
        total_orders = await orders_col.count_documents({})
        total_users = await users_col.count_documents({"role": "customer"})

        # Named explicitly: revenue excluding cancelled orders (a cancelled order was never
        # actually fulfilled/paid for, so it shouldn't inflate revenue). See NOTES_schema_audit.md §9.
        revenue_agg = await orders_col.aggregate([
            {"$match": {"status": {"$ne": "cancelled"}}},
            {"$group": {"_id": None, "total_revenue": {"$sum": "$total"}}}
        ]).to_list(length=1)
        total_revenue = revenue_agg[0]["total_revenue"] if revenue_agg else 0

        pending_orders = await orders_col.count_documents({"status": "pending"})

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
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Legacy stats error: {e}", {"endpoint": "legacy_stats"})
        logger.error(f"Legacy stats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch stats")


@router.get("/dashboard/summary")
@limiter.limit("30/minute")
async def dashboard_summary(request: Request, _=Depends(verify_admin_token)):
    """Get the combined dashboard summary payload for charts and KPIs."""
    try:
        cache_key = "admin:dashboard:summary"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        total_products = await products_col.count_documents({})
        active_products = await products_col.count_documents({"is_active": True})

        total_orders = await orders_col.count_documents({})
        total_users = await users_col.count_documents({})
        active_users = await users_col.count_documents({"is_active": True})
        banned_users = await users_col.count_documents({"is_banned": True})

        status_agg = await orders_col.aggregate([
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                    "revenue": {"$sum": "$total"},
                }
            }
        ]).to_list(length=20)
        # status_agg (and the orders_by_status/revenue_by_status chart data built from it below)
        # intentionally keeps every status, including cancelled — that breakdown is exactly where
        # an admin would want to see cancelled-order revenue. The single total_revenue KPI is a
        # different question ("how much did we actually make") and must exclude it.
        total_revenue = round(
            sum(float(item["revenue"] or 0) for item in status_agg if item["_id"] != "cancelled"), 2
        )

        product_agg = await orders_col.aggregate([
            {"$unwind": "$items"},
            {
                "$group": {
                    "_id": "$items.product_id",
                    "name": {"$first": "$items.name"},
                    "quantity_sold": {"$sum": "$items.quantity"},
                    "revenue": {"$sum": {"$multiply": ["$items.quantity", "$items.price"]}},
                }
            },
            {"$sort": {"revenue": -1}},
            {"$limit": 5},
        ]).to_list(length=5)

        recent_orders = await orders_col.find({}, {"order_number": 1, "status": 1, "total": 1, "created_at": 1, "user_id": 1}) \
            .sort("created_at", -1) \
            .limit(5) \
            .to_list(length=5)

        monthly_growth = await users_col.aggregate([
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m",
                            "date": {"$toDate": "$created_at"}
                        }
                    },
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}},
            {"$limit": 12}
        ]).to_list(length=12)

        payload = {
            "stats": {
                "total_products": total_products,
                "active_products": active_products,
                "total_orders": total_orders,
                "total_revenue": total_revenue,
                "pending_orders": next((item["count"] for item in status_agg if item["_id"] == "pending"), 0),
                "total_users": total_users,
                "active_users": active_users,
                "banned_users": banned_users,
            },
            "orders_by_status": [
                {"status": item["_id"], "count": item["count"]}
                for item in sorted(status_agg, key=lambda item: item["_id"] or "")
            ],
            "revenue_by_status": [
                {"status": item["_id"], "revenue": round(float(item["revenue"] or 0), 2)}
                for item in sorted(status_agg, key=lambda item: item["_id"] or "")
            ],
            "top_products": [
                {
                    "product_id": str(item["_id"]),
                    "name": item["name"],
                    "quantity_sold": item["quantity_sold"],
                    "revenue": round(float(item["revenue"]), 2),
                }
                for item in product_agg
            ],
            "monthly_growth": [
                {"month": item["_id"], "signups": item["count"]}
                for item in monthly_growth
            ],
            "recent_orders": [
                {
                    "order_id": str(order.get("_id", "")),
                    "order_number": order.get("order_number") or str(order.get("_id", ""))[:8],
                    "status": order.get("status"),
                    "total": round(float(order.get("total", 0) or 0), 2),
                    "created_at": order.get("created_at"),
                }
                for order in recent_orders
            ],
        }
        await cache_set(cache_key, payload, ttl_seconds=45)
        return payload
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Dashboard summary error: {e}", {"endpoint": "dashboard_summary"})
        logger.error(f"Dashboard summary error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard summary")

@router.get("/analytics/revenue")
@limiter.limit("30/minute")
async def revenue_analytics(request: Request, _=Depends(verify_admin_token)):
    """Get revenue analytics (total and by status)"""
    try:
        # Revenue by order status
        pipeline = [
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                    "revenue": {"$sum": "$total"}
                }
            },
            {"$sort": {"revenue": -1}}
        ]
        status_revenue = await orders_col.aggregate(pipeline).to_list(length=10)

        # Same "excludes cancelled" semantic as legacy_stats/dashboard_summary — see NOTES_schema_audit.md §9.
        total_revenue_agg = await orders_col.aggregate([
            {"$match": {"status": {"$ne": "cancelled"}}},
            {"$group": {"_id": None, "total": {"$sum": "$total"}}}
        ]).to_list(length=1)
        total_revenue = total_revenue_agg[0]["total"] if total_revenue_agg else 0

        top_products = await orders_col.aggregate([
            {"$unwind": "$items"},
            {
                "$group": {
                    "_id": "$items.product_id",
                    "name": {"$first": "$items.name"},
                    "quantity": {"$sum": "$items.quantity"},
                    "revenue": {"$sum": {"$multiply": ["$items.quantity", "$items.price"]}},
                }
            },
            {"$sort": {"revenue": -1}},
            {"$limit": 5},
        ]).to_list(length=5)
        
        return {
            "total_revenue": round(total_revenue, 2),
            "by_status": [
                {
                    "status": s["_id"],
                    "count": s["count"],
                    "revenue": round(s["revenue"], 2)
                }
                for s in status_revenue
            ],
            "top_products": [
                {
                    "product_id": str(p["_id"]),
                    "name": p["name"],
                    "quantity_sold": p["quantity"],
                    "revenue": round(p["revenue"], 2)
                }
                for p in top_products
            ]
        }
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Revenue analytics error: {e}", {"endpoint": "revenue_analytics"})
        logger.error(f"Revenue analytics error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch revenue analytics")

@router.get("/analytics/orders")
@limiter.limit("30/minute")
async def order_analytics(request: Request, _=Depends(verify_admin_token)):
    """Get order analytics by status"""
    try:
        pipeline = [
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }
            }
        ]
        status_counts = await orders_col.aggregate(pipeline).to_list(length=10)
        
        status_map = {s["_id"]: s["count"] for s in status_counts}
        
        return {
            "total_orders": sum(status_map.values()),
            "pending": status_map.get("pending", 0),
            "confirmed": status_map.get("confirmed", 0),
            "packed": status_map.get("packed", 0),
            "shipped": status_map.get("shipped", 0),
            "delivered": status_map.get("delivered", 0),
            "cancelled": status_map.get("cancelled", 0),
        }
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Order analytics error: {e}", {"endpoint": "order_analytics"})
        logger.error(f"Order analytics error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch order analytics")

@router.get("/analytics/users")
@limiter.limit("30/minute")
async def user_analytics(request: Request, _=Depends(verify_admin_token)):
    """Get user analytics (growth, active users)"""
    try:
        total_users = await users_col.count_documents({})
        active_users = await users_col.count_documents({"is_active": True})
        banned_users = await users_col.count_documents({"is_banned": True})
        
        # User growth by month (created_at)
        pipeline = [
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m",
                            "date": {"$toDate": "$created_at"}
                        }
                    },
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}},
            {"$limit": 12}
        ]
        monthly_growth = await users_col.aggregate(pipeline).to_list(length=12)
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "banned_users": banned_users,
            "inactive_users": total_users - active_users,
            "monthly_growth": [
                {
                    "month": m["_id"],
                    "signups": m["count"]
                }
                for m in monthly_growth
            ]
        }
    except Exception as e:
        await log_to_db("ERROR", __name__, f"User analytics error: {e}", {"endpoint": "user_analytics"})
        logger.error(f"User analytics error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch user analytics")

# ════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION ROUTES
# ════════════════════════════════════════════════════════════════════════════

REFRESH_COOKIE_NAME = "admin_refresh_token"
REFRESH_COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days, matches jwt_refresh_expire_minutes default


CSRF_COOKIE_NAME = "admin_csrf_token"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=REFRESH_COOKIE_MAX_AGE,
    )
    # Double-submit CSRF cookie, rotated alongside the refresh cookie — see utils/csrf.py.
    # POST /admin/auth/refresh is the only admin endpoint that authenticates purely off a cookie
    # (no bearer header), so it's the one that needs this; /admin/auth/logout already requires
    # verify_admin_token.
    set_csrf_cookie(response, CSRF_COOKIE_NAME, generate_csrf_token(), settings.cookie_secure, REFRESH_COOKIE_MAX_AGE)


@router.post("/auth/login")
async def login(credentials: AdminLogin, request: Request, response: Response):
    """Admin login.

    Refresh token contract matches the customer flow (routes/auth.py): httpOnly cookie, never
    exposed to JS, rather than the old admin-only pattern of returning it in the JSON body for
    localStorage storage (which was reachable by any XSS on the page). A distinct cookie name
    ("admin_refresh_token" vs "refresh_token") avoids the two sessions clobbering each other when
    both the admin panel and customer site are open in the same browser on the same origin. See
    NOTES_schema_audit.md §7.
    """
    try:
        result = await AdminAuthService.authenticate(
            email=credentials.email,
            password=credentials.password,
            ip_address=request.client.host if request.client else "0.0.0.0"
        )
        _set_refresh_cookie(response, result.pop("refresh_token"))
        return {
            "success": True,
            "message": "Login successful",
            "data": result
        }
    except HTTPException as e:
        logger.warning(f"Login failed for {credentials.email}")
        raise
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Login error: {e}", {"email": credentials.email})
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")

@router.post("/auth/refresh")
async def refresh(request: Request, response: Response):
    """Refresh access token using the httpOnly refresh cookie set at login."""
    refresh_token_str = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token_str:
        raise HTTPException(status_code=401, detail="No refresh token")

    verify_csrf(request, CSRF_COOKIE_NAME)

    try:
        result = await AdminAuthService.refresh_token(refresh_token_str)
        _set_refresh_cookie(response, result.pop("refresh_token"))
        return {
            "success": True,
            "message": "Token refreshed",
            "data": result
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Refresh error: {e}")
        logger.error(f"Refresh error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

@router.post("/auth/logout")
async def logout(request: Request, response: Response, admin_data: dict = Depends(verify_admin_token)):
    """Admin logout"""
    try:
        await AdminAuthService.logout(
            admin_id=admin_data["admin_id"],
            ip_address=request.state.ip_address
        )
        response.delete_cookie(REFRESH_COOKIE_NAME, httponly=True, secure=settings.cookie_secure, samesite="strict")
        response.delete_cookie(CSRF_COOKIE_NAME, httponly=False, secure=settings.cookie_secure, samesite="strict")
        return {
            "success": True,
            "message": "Logout successful"
        }
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Logout error: {e}", {"admin_id": admin_data.get("admin_id") if isinstance(admin_data, dict) else None})
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(status_code=500, detail="Logout failed")

@router.post("/auth/change-password")
async def change_password(
    body: AdminChangePasswordRequest,
    admin_data: dict = Depends(verify_admin_token)
):
    """Change admin password. Body, not query params — mirrors routes/auth.py's ChangePasswordRequest."""
    try:
        await AdminAuthService.change_password(
            admin_id=admin_data["admin_id"],
            old_password=body.old_password,
            new_password=body.new_password
        )
        return {
            "success": True,
            "message": "Password changed successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Password change error: {e}", {"admin_id": admin_data.get("admin_id") if isinstance(admin_data, dict) else None})
        logger.error(f"Password change error: {str(e)}")
        raise HTTPException(status_code=500, detail="Password change failed")

@router.post("/auth/unlock/{admin_id}")
async def unlock_admin_account(admin_id: str, admin_data: dict = Depends(verify_admin_token)):
    """Unlock a locked admin account. Super-admin only — "admin:update" is reserved for
    super_admin in utils/permissions.py. AdminAuthService.unlock_account already existed but had
    no route calling it. See NOTES_schema_audit.md §7."""
    if not await check_permission(admin_data, "admin:update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        await AdminAuthService.unlock_account(admin_id=admin_id, super_admin_id=admin_data["admin_id"])
        return {"success": True, "message": "Account unlocked"}
    except HTTPException:
        raise
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Unlock account error: {e}", {"target_admin_id": admin_id})
        logger.error(f"Unlock account error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to unlock account")

# ════════════════════════════════════════════════════════════════════════════
# PRODUCT ROUTES
# ════════════════════════════════════════════════════════════════════════════

@router.post("/products")
async def create_product(
    product: ProductCreate,
    request: Request,
    admin_data: dict = Depends(verify_admin_token)
):
    """Create new product"""
    if not await check_permission(admin_data, "product:create"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        product_id = await ProductService.create_product(
            name=product.name,
            description=product.description,
            category=product.category,
            price=product.price,
            discount_percentage=product.discount_percentage,
            variants=[v.model_dump() for v in product.variants],
            tags=product.tags,
            images=product.images,
            admin_id=admin_data["admin_id"],
        )
        await cache_clear_prefix("products:list:")
        await cache_delete("products:categories")
        return {
            "success": True,
            "message": "Product created successfully",
            "data": {"product_id": product_id}
        }
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Product creation error: {e}", {"admin_id": admin_data.get("admin_id") if isinstance(admin_data, dict) else None})
        logger.error(f"Product creation error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create product")

@router.get("/products/{product_id}")
async def get_product(
    product_id: str,
    admin_data: dict = Depends(verify_admin_token)
):
    """Get product details"""
    if not await check_permission(admin_data, "product:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        product = await ProductService.get_product(product_id)
        return {
            "success": True,
            "data": product
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Get product error: {e}", {"product_id": product_id})
        logger.error(f"Get product error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch product")

@router.put("/products/{product_id}")
async def update_product(
    product_id: str,
    product: ProductUpdate,
    request: Request,
    admin_data: dict = Depends(verify_admin_token)
):
    """Update product"""
    if not await check_permission(admin_data, "product:update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        updates = product.model_dump(exclude_unset=True)
        if "variants" in updates:
            updates["variants"] = [v.model_dump() if hasattr(v, "model_dump") else v for v in updates["variants"]]
        
        updated = await ProductService.update_product(
            product_id=product_id,
            updates=updates,
            admin_id=admin_data["admin_id"],
        )
        await cache_clear_prefix("products:list:")
        await cache_delete("products:categories")
        return {
            "success": True,
            "message": "Product updated successfully",
            "data": updated
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Product update error: {e}", {"product_id": product_id, "admin_id": admin_data.get("admin_id") if isinstance(admin_data, dict) else None})
        logger.error(f"Product update error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update product")

@router.delete("/products/{product_id}")
async def delete_product(
    product_id: str,
    admin_data: dict = Depends(verify_admin_token)
):
    """Delete (soft) product"""
    if not await check_permission(admin_data, "product:delete"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        await ProductService.delete_product(product_id, admin_data["admin_id"])
        await cache_clear_prefix("products:list:")
        await cache_delete("products:categories")
        return {
            "success": True,
            "message": "Product deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Product deletion error: {e}", {"product_id": product_id})
        logger.error(f"Product deletion error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete product")

@router.get("/products")
async def list_products(
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 50,
    skip: int = 0,
    admin_data: dict = Depends(verify_admin_token)
):
    """List products"""
    if not await check_permission(admin_data, "product:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        products, total = await ProductService.list_products(
            category=category,
            is_active=is_active,
            limit=limit,
            skip=skip
        )
        return {
            "success": True,
            "data": products,
            "total": total,
            "limit": limit,
            "skip": skip
        }
    except Exception as e:
        await log_to_db("ERROR", __name__, f"List products error: {e}")
        logger.error(f"List products error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch products")

@router.get("/products/low-stock/items")
async def get_low_stock(
    admin_data: dict = Depends(verify_admin_token)
):
    """Get low stock items"""
    if not await check_permission(admin_data, "inventory:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        items = await ProductService.get_low_stock_items()
        return {
            "success": True,
            "data": items,
            "count": len(items)
        }
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Low stock error: {e}")
        logger.error(f"Low stock error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch low stock items")

# ════════════════════════════════════════════════════════════════════════════
# INVENTORY ROUTES
# ════════════════════════════════════════════════════════════════════════════

@router.post("/inventory/adjust-stock")
async def adjust_stock(
    product_id: str,
    variant_sku: str,
    quantity_change: int,
    reason: str,
    admin_data: dict = Depends(verify_admin_token)
):
    """Adjust stock for variant"""
    if not await check_permission(admin_data, "inventory:update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        await InventoryService.adjust_stock(
            product_id=product_id,
            variant_sku=variant_sku,
            quantity_change=quantity_change,
            reason=reason,
            admin_id=admin_data["admin_id"],
        )
        return {
            "success": True,
            "message": "Stock adjusted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Stock adjustment error: {e}", {"product_id": product_id})
        logger.error(f"Stock adjustment error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to adjust stock")

@router.get("/inventory/history/{product_id}")
async def get_inventory_history(
    product_id: str,
    limit: int = 100,
    admin_data: dict = Depends(verify_admin_token)
):
    """Get inventory history for product"""
    if not await check_permission(admin_data, "inventory:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        history = await InventoryService.get_inventory_history(product_id, limit)
        return {
            "success": True,
            "data": history
        }
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Inventory history error: {e}", {"product_id": product_id})
        logger.error(f"Inventory history error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch inventory history")

# ════════════════════════════════════════════════════════════════════════════
# ORDER ROUTES
# ════════════════════════════════════════════════════════════════════════════

@router.get("/orders/{order_id}")
async def get_order(
    order_id: str,
    admin_data: dict = Depends(verify_admin_token)
):
    """Get order details"""
    if not await check_permission(admin_data, "order:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        order = await OrderService.get_order(order_id)
        return {
            "success": True,
            "data": order
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Get order error: {e}", {"order_id": order_id})
        logger.error(f"Get order error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch order")

@router.put("/orders/{order_id}/status")
async def update_order_status(
    order_id: str,
    update: OrderStatusUpdate,
    request: Request,
    admin_data: dict = Depends(verify_admin_token)
):
    """Update order status"""
    if not await check_permission(admin_data, "order:update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        order = await OrderService.update_order_status(
            order_id=order_id,
            new_status=update.status,
            note=update.note,
            admin_id=admin_data["admin_id"],
        )
        return {
            "success": True,
            "message": "Order status updated",
            "data": order
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Order status update error: {e}", {"order_id": order_id, "admin_id": admin_data.get("admin_id") if isinstance(admin_data, dict) else None})
        logger.error(f"Order status update error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update order status")

@router.get("/orders")
async def list_orders(
    status: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    admin_data: dict = Depends(verify_admin_token)
):
    """List orders"""
    if not await check_permission(admin_data, "order:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        orders, total = await OrderService.list_orders(
            status=status,
            user_id=user_id,
            limit=limit,
            skip=skip
        )
        return {
            "success": True,
            "data": orders,
            "total": total,
            "limit": limit,
            "skip": skip
        }
    except Exception as e:
        await log_to_db("ERROR", __name__, f"List orders error: {e}")
        logger.error(f"List orders error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch orders")

@router.post("/orders/{order_id}/note")
async def add_order_note(
    order_id: str,
    note: str,
    admin_data: dict = Depends(verify_admin_token)
):
    """Add note to order"""
    if not await check_permission(admin_data, "order:update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        order = await OrderService.add_order_note(
            order_id=order_id,
            note=note,
            admin_id=admin_data["admin_id"],
        )
        return {
            "success": True,
            "message": "Note added",
            "data": order
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Add note error: {e}", {"order_id": order_id})
        logger.error(f"Add note error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to add note")

# ════════════════════════════════════════════════════════════════════════════
# USER MANAGEMENT ROUTES
# ════════════════════════════════════════════════════════════════════════════

@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    admin_data: dict = Depends(verify_admin_token)
):
    """Get user details"""
    if not await check_permission(admin_data, "user:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        user = await UserService.get_user(user_id)
        return {
            "success": True,
            "data": user
        }
    except HTTPException:
        raise
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Get user error: {e}", {"user_id": user_id})
        logger.error(f"Get user error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch user")

@router.get("/users")
async def list_users(
    is_banned: Optional[bool] = None,
    limit: int = 50,
    skip: int = 0,
    admin_data: dict = Depends(verify_admin_token)
):
    """List users"""
    if not await check_permission(admin_data, "user:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        users, total = await UserService.list_users(
            is_banned=is_banned,
            limit=limit,
            skip=skip
        )
        return {
            "success": True,
            "data": users,
            "total": total,
            "limit": limit,
            "skip": skip
        }
    except Exception as e:
        logger.error(f"List users error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch users")

@router.post("/users/{user_id}/ban")
async def ban_user(
    user_id: str,
    reason: str,
    admin_data: dict = Depends(verify_admin_token)
):
    """Ban user"""
    if not await check_permission(admin_data, "user:ban"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        user = await UserService.ban_user(
            user_id=user_id,
            reason=reason,
            admin_id=admin_data["admin_id"],
        )
        return {
            "success": True,
            "message": "User banned",
            "data": user
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ban user error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to ban user")

@router.post("/users/{user_id}/unban")
async def unban_user(
    user_id: str,
    admin_data: dict = Depends(verify_admin_token)
):
    """Unban user"""
    if not await check_permission(admin_data, "user:ban"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        user = await UserService.unban_user(
            user_id=user_id,
            admin_id=admin_data["admin_id"],
        )
        return {
            "success": True,
            "message": "User unbanned",
            "data": user
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unban user error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to unban user")

@router.get("/users/{user_id}/orders")
async def get_user_orders(
    user_id: str,
    limit: int = 20,
    admin_data: dict = Depends(verify_admin_token)
):
    """Get user's order history"""
    if not await check_permission(admin_data, "user:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        orders = await UserService.get_user_order_history(user_id, limit)
        return {
            "success": True,
            "data": orders,
            "count": len(orders)
        }
    except Exception as e:
        logger.error(f"Get user orders error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch user orders")

# ════════════════════════════════════════════════════════════════════════════
# RIDER MANAGEMENT ROUTES
# ════════════════════════════════════════════════════════════════════════════

@router.post("/riders")
async def create_rider(rider: RiderCreate, admin_data: dict = Depends(verify_admin_token)):
    """Create a new rider account"""
    if not await check_permission(admin_data, "rider:create"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        created = await RiderService.create_rider(
            name=rider.name, email=rider.email, password=rider.password,
            phone=rider.phone, admin_id=admin_data["admin_id"],
        )
        return {"success": True, "message": "Rider created successfully", "data": created}
    except HTTPException:
        raise
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Rider creation error: {e}", {"admin_id": admin_data.get("admin_id")})
        logger.error(f"Rider creation error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create rider")

@router.get("/riders")
async def list_riders(is_active: Optional[bool] = None, admin_data: dict = Depends(verify_admin_token)):
    """List riders with their live status/availability"""
    if not await check_permission(admin_data, "rider:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        riders = await RiderService.list_riders(is_active=is_active)
        return {"success": True, "data": riders, "total": len(riders)}
    except Exception as e:
        logger.error(f"List riders error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch riders")

@router.get("/riders/{rider_id}/active-orders")
async def get_rider_active_orders(rider_id: str, admin_data: dict = Depends(verify_admin_token)):
    """Count of a rider's currently active (not delivered/cancelled) orders"""
    if not await check_permission(admin_data, "rider:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        count = await RiderService.get_active_order_count(rider_id)
        return {"success": True, "data": {"rider_id": rider_id, "active_orders": count}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rider active-orders error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch rider's active orders")

@router.patch("/riders/{rider_id}/activate")
async def activate_rider(rider_id: str, admin_data: dict = Depends(verify_admin_token)):
    """Activate a rider account"""
    if not await check_permission(admin_data, "rider:update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        updated = await RiderService.set_active(rider_id, True, admin_data["admin_id"])
        return {"success": True, "message": "Rider activated", "data": updated}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Activate rider error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to activate rider")

@router.patch("/riders/{rider_id}/deactivate")
async def deactivate_rider(rider_id: str, admin_data: dict = Depends(verify_admin_token)):
    """Deactivate a rider account"""
    if not await check_permission(admin_data, "rider:update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        updated = await RiderService.set_active(rider_id, False, admin_data["admin_id"])
        return {"success": True, "message": "Rider deactivated", "data": updated}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Deactivate rider error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to deactivate rider")

@router.patch("/orders/{order_id}/assign-rider")
async def assign_rider(order_id: str, rider_id: str, admin_data: dict = Depends(verify_admin_token)):
    """Assign a rider to an order (admin only).

    Canonical assign-rider path — validates the rider exists and is active/available, and that
    the order isn't already delivered/cancelled, before assigning. Replaces the old
    routes/orders.py::assign_rider, which had neither check and was gated by the customer-facing
    JWT auth path instead of the admin permission matrix. See NOTES_schema_audit.md §4.
    """
    if not await check_permission(admin_data, "order:update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        oid = ObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid order ID")

    order = await orders_col.find_one({"_id": oid})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["status"] in ("delivered", "cancelled", "returned"):
        raise HTTPException(status_code=400, detail=f"Cannot assign a rider to a {order['status']} order")

    if not await RiderService.is_available_for_assignment(rider_id):
        raise HTTPException(status_code=400, detail="Rider does not exist or is not active/available")

    await orders_col.update_one(
        {"_id": oid},
        {"$set": {"rider_id": rider_id, "updated_at": datetime.utcnow()}},
    )
    return {"success": True, "message": "Rider assigned"}

# ════════════════════════════════════════════════════════════════════════════
# DISCOUNT ROUTES
# ════════════════════════════════════════════════════════════════════════════

@router.post("/discounts")
async def create_discount(
    discount: DiscountCreate,
    admin_data: dict = Depends(verify_admin_token)
):
    """Create new discount"""
    if not await check_permission(admin_data, "promo:create"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        discount_id = await DiscountService.create_discount(
            code=discount.code,
            description=discount.description,
            discount_type=discount.discount_type,
            discount_value=discount.discount_value,
            max_usage=discount.max_usage,
            min_order_value=discount.min_order_value,
            expiry_date=discount.expiry_date,
            admin_id=admin_data["admin_id"],
        )
        return {
            "success": True,
            "message": "Discount created",
            "data": {"discount_id": discount_id}
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create discount error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create discount")

@router.get("/discounts/{discount_id}")
async def get_discount(
    discount_id: str,
    admin_data: dict = Depends(verify_admin_token)
):
    """Get discount details"""
    if not await check_permission(admin_data, "promo:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        discount = await DiscountService.get_discount(discount_id)
        return {
            "success": True,
            "data": discount
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get discount error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch discount")

@router.put("/discounts/{discount_id}")
async def update_discount(
    discount_id: str,
    update: DiscountUpdate,
    admin_data: dict = Depends(verify_admin_token)
):
    """Update discount"""
    if not await check_permission(admin_data, "promo:update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        updates = update.model_dump(exclude_unset=True)
        discount = await DiscountService.update_discount(
            discount_id=discount_id,
            updates=updates,
            admin_id=admin_data["admin_id"],
        )
        return {
            "success": True,
            "message": "Discount updated",
            "data": discount
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update discount error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update discount")

@router.get("/discounts")
async def list_discounts(
    is_active: Optional[bool] = None,
    limit: int = 50,
    skip: int = 0,
    admin_data: dict = Depends(verify_admin_token)
):
    """List discounts"""
    if not await check_permission(admin_data, "promo:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        discounts, total = await DiscountService.list_discounts(
            is_active=is_active,
            limit=limit,
            skip=skip
        )
        return {
            "success": True,
            "data": discounts,
            "total": total,
            "limit": limit,
            "skip": skip
        }
    except Exception as e:
        logger.error(f"List discounts error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch discounts")

# ════════════════════════════════════════════════════════════════════════════
# DASHBOARD ROUTES
# ════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard/stats")
async def get_stats(
    admin_data: dict = Depends(verify_admin_token)
):
    """Get dashboard statistics"""
    if not await check_permission(admin_data, "dashboard:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        stats = await DashboardService.get_dashboard_stats()
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        logger.error(f"Get stats error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch statistics")

@router.get("/dashboard/revenue-trend")
async def get_revenue_trend(
    days: int = 30,
    admin_data: dict = Depends(verify_admin_token)
):
    """Get revenue trend"""
    if not await check_permission(admin_data, "dashboard:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        trend = await DashboardService.get_revenue_trend(days)
        return {
            "success": True,
            "data": trend
        }
    except Exception as e:
        logger.error(f"Get revenue trend error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch revenue trend")

@router.get("/dashboard/top-products")
async def get_top_products(
    limit: int = 10,
    admin_data: dict = Depends(verify_admin_token)
):
    """Get top selling products"""
    if not await check_permission(admin_data, "dashboard:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        products = await DashboardService.get_top_products(limit)
        return {
            "success": True,
            "data": products
        }
    except Exception as e:
        logger.error(f"Get top products error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch top products")

@router.get("/dashboard/low-stock")
async def get_low_stock_dashboard(
    admin_data: dict = Depends(verify_admin_token)
):
    """Get low stock items for dashboard"""
    if not await check_permission(admin_data, "dashboard:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        items = await DashboardService.get_low_stock_items()
        return {
            "success": True,
            "data": items,
            "count": len(items)
        }
    except Exception as e:
        logger.error(f"Get low stock error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch low stock items")

@router.get("/dashboard/recent-orders")
async def get_recent_orders_dashboard(
    limit: int = 10,
    admin_data: dict = Depends(verify_admin_token)
):
    """Get recent orders for dashboard"""
    if not await check_permission(admin_data, "dashboard:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        orders = await DashboardService.get_recent_orders(limit)
        return {
            "success": True,
            "data": orders,
            "count": len(orders)
        }
    except Exception as e:
        logger.error(f"Get recent orders error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch recent orders")

# ════════════════════════════════════════════════════════════════════════════
# AUDIT LOG ROUTES
# ════════════════════════════════════════════════════════════════════════════

@router.get("/audit-logs")
async def get_audit_logs(
    entity_type: Optional[str] = None,
    admin_id: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    admin_data: dict = Depends(verify_admin_token)
):
    """Get audit logs"""
    if not await check_permission(admin_data, "audit:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        logs, total = await AdminAuditService.get_logs(
            entity_type=entity_type,
            admin_id=admin_id,
            limit=limit,
            skip=skip
        )
        return {
            "success": True,
            "data": logs,
            "total": total,
            "limit": limit,
            "skip": skip
        }
    except Exception as e:
        logger.error(f"Get audit logs error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch audit logs")
