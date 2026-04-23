from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from middleware.admin_auth import verify_admin_token, check_permission
from schemas.admin import *
from services.admin_auth import AdminAuthService, AdminAuditService
from services.product import ProductService, InventoryService
from services.order_user import OrderService, UserService
from services.discount import DiscountService
from services.dashboard import DashboardService
from typing import Optional
import logging

logger = logging.getLogger("admin_routes")

router = APIRouter(prefix="/admin", tags=["Admin"])
security = HTTPBearer()

# ════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION ROUTES
# ════════════════════════════════════════════════════════════════════════════

@router.post("/auth/login")
async def login(credentials: AdminLogin, request: Request):
    """Admin login"""
    try:
        result = await AdminAuthService.authenticate(
            email=credentials.email,
            password=credentials.password,
            ip_address=request.client.host if request.client else "0.0.0.0"
        )
        return {
            "success": True,
            "message": "Login successful",
            "data": result
        }
    except HTTPException as e:
        logger.warning(f"Login failed for {credentials.email}")
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")

@router.post("/auth/refresh")
async def refresh(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Refresh access token"""
    try:
        result = await AdminAuthService.refresh_token(credentials.credentials)
        return {
            "success": True,
            "message": "Token refreshed",
            "data": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Refresh error: {str(e)}")
        raise HTTPException(status_code=500, detail="Token refresh failed")

@router.post("/auth/logout")
async def logout(request: Request, admin_data: dict = Depends(verify_admin_token)):
    """Admin logout"""
    try:
        await AdminAuthService.logout(
            admin_id=admin_data["admin_id"],
            ip_address=request.state.ip_address
        )
        return {
            "success": True,
            "message": "Logout successful"
        }
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(status_code=500, detail="Logout failed")

@router.post("/auth/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    admin_data: dict = Depends(verify_admin_token)
):
    """Change admin password"""
    try:
        await AdminAuthService.change_password(
            admin_id=admin_data["admin_id"],
            old_password=old_password,
            new_password=new_password
        )
        return {
            "success": True,
            "message": "Password changed successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change error: {str(e)}")
        raise HTTPException(status_code=500, detail="Password change failed")

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
        return {
            "success": True,
            "message": "Product created successfully",
            "data": {"product_id": product_id}
        }
    except Exception as e:
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
        return {
            "success": True,
            "message": "Product updated successfully",
            "data": updated
        }
    except HTTPException:
        raise
    except Exception as e:
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
        return {
            "success": True,
            "message": "Product deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
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
