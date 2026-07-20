from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, status, Request, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db.order import Order, OrderItem
from db.product import Product
from db.return_request import ReturnRequest
from db.user import User
from middleware.admin_auth import verify_admin_token, check_permission
from schemas.admin import *
from services.admin_auth import AdminAuthService, AdminAuditService
from services.product import ProductService, InventoryService
from services.order_user import OrderService, UserService
from services.discount import DiscountService
from services.dashboard import DashboardService
from services.rider import RiderService
from services.image_storage import ImageStorageService
from services.return_request import _return_request_to_dict, resolve_return_request
from services.csv_io import bulk_update_order_status_csv, export_orders_csv, export_products_csv, import_products_csv
from services.reports import generate_sales_inventory_report
from schemas.rider import RiderCreate
from schemas.upload import ImageUploadResponse
from schemas.return_request import ReturnRequestListResponse, ReturnRequestResolve, ReturnRequestResponse
from utils.logger import get_logger, log_to_db
from utils.cache import cache_get, cache_set, cache_clear_prefix, cache_delete
from utils.ids import is_valid_id
from config import settings
from utils.limiter import limiter
from utils.csrf import generate_csrf_token, set_csrf_cookie, verify_csrf
from utils.helpers import sanitize_input
from utils.token_revocation import revoke_jti

logger = get_logger(__name__)

# Router intentionally has no internal prefix — main.py mounts it with prefix="/admin"
router = APIRouter(tags=["Admin"])


# Simple stats endpoint (kept from legacy admin module) mounted at /admin/stats
@router.get("/stats")
@limiter.limit("30/minute")
async def legacy_stats(request: Request, _=Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    """Get admin dashboard statistics (admin only)"""
    try:
        total_products = (await db.execute(select(func.count()).select_from(Product).where(Product.is_active == True))).scalar_one()  # noqa: E712
        total_orders = (await db.execute(select(func.count()).select_from(Order))).scalar_one()
        total_users = (await db.execute(select(func.count()).select_from(User).where(User.role == "customer"))).scalar_one()

        # Named explicitly: revenue excluding cancelled orders (a cancelled order was never
        # actually fulfilled/paid for, so it shouldn't inflate revenue). See NOTES_schema_audit.md §9.
        total_revenue = (await db.execute(
            select(func.coalesce(func.sum(Order.total), 0)).where(Order.status != "cancelled")
        )).scalar_one()

        pending_orders = (await db.execute(select(func.count()).select_from(Order).where(Order.status == "pending"))).scalar_one()

        cat_result = await db.execute(
            select(Product.category, func.count().label("count"))
            .group_by(Product.category).order_by(func.count().desc()).limit(5)
        )
        categories = cat_result.all()

        return {
            "total_products": total_products,
            "total_orders": total_orders,
            "total_users": total_users,
            "total_revenue": round(total_revenue, 2),
            "pending_orders": pending_orders,
            "top_categories": [{"category": c.category, "count": c.count} for c in categories]
        }
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Legacy stats error: {e}", {"endpoint": "legacy_stats"})
        logger.error(f"Legacy stats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch stats")


@router.get("/dashboard/summary")
@limiter.limit("30/minute")
async def dashboard_summary(request: Request, _=Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    """Get the combined dashboard summary payload for charts and KPIs."""
    try:
        cache_key = "admin:dashboard:summary"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        total_products = (await db.execute(select(func.count()).select_from(Product))).scalar_one()
        active_products = (await db.execute(select(func.count()).select_from(Product).where(Product.is_active == True))).scalar_one()  # noqa: E712

        total_orders = (await db.execute(select(func.count()).select_from(Order))).scalar_one()
        total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
        active_users = (await db.execute(select(func.count()).select_from(User).where(User.is_active == True))).scalar_one()  # noqa: E712
        banned_users = (await db.execute(select(func.count()).select_from(User).where(User.is_banned == True))).scalar_one()  # noqa: E712

        status_result = await db.execute(
            select(Order.status, func.count().label("count"), func.sum(Order.total).label("revenue")).group_by(Order.status)
        )
        status_agg = status_result.all()
        # status_agg (and the orders_by_status/revenue_by_status chart data built from it below)
        # intentionally keeps every status, including cancelled — that breakdown is exactly where
        # an admin would want to see cancelled-order revenue. The single total_revenue KPI is a
        # different question ("how much did we actually make") and must exclude it.
        total_revenue = round(
            sum(float(row.revenue or 0) for row in status_agg if row.status != "cancelled"), 2
        )

        # Trend indicators: current vs previous 30-day window. Cancelled orders excluded from
        # both revenue and the order count, same exclusion total_revenue already applies, so the
        # two numbers stay comparable. None (not 0%) when the previous window has no orders at
        # all — a percentage change from zero is undefined, not honestly representable as a number.
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=30)
        prev_period_start = now - timedelta(days=60)

        current_period = (await db.execute(
            select(
                func.coalesce(func.sum(Order.total), 0).label("revenue"),
                func.count().label("orders"),
            ).where(Order.created_at >= period_start, Order.status != "cancelled")
        )).one()

        previous_period = (await db.execute(
            select(
                func.coalesce(func.sum(Order.total), 0).label("revenue"),
                func.count().label("orders"),
            ).where(
                Order.created_at >= prev_period_start,
                Order.created_at < period_start,
                Order.status != "cancelled",
            )
        )).one()

        def _pct_change(current, previous):
            current = float(current or 0)
            previous = float(previous or 0)
            if previous == 0:
                return None
            return round((current - previous) / previous * 100, 1)

        revenue_trend_pct = _pct_change(current_period.revenue, previous_period.revenue)
        orders_trend_pct = _pct_change(current_period.orders, previous_period.orders)

        product_result = await db.execute(
            select(
                OrderItem.product_id,
                func.any_value(OrderItem.name).label("name"),
                func.sum(OrderItem.quantity).label("quantity_sold"),
                func.sum(OrderItem.quantity * OrderItem.price).label("revenue"),
            )
            .group_by(OrderItem.product_id).order_by(func.sum(OrderItem.quantity * OrderItem.price).desc()).limit(5)
        )
        product_agg = product_result.all()

        recent_result = await db.execute(select(Order).order_by(Order.created_at.desc()).limit(5))
        recent_orders = recent_result.scalars().all()

        month_bucket = func.date_format(User.created_at, "%Y-%m")
        growth_result = await db.execute(
            select(month_bucket.label("month"), func.count().label("count"))
            .group_by(month_bucket).order_by(month_bucket).limit(12)
        )
        monthly_growth = growth_result.all()

        payload = {
            "stats": {
                "total_products": total_products,
                "active_products": active_products,
                "total_orders": total_orders,
                "total_revenue": total_revenue,
                "pending_orders": next((row.count for row in status_agg if row.status == "pending"), 0),
                "total_users": total_users,
                "active_users": active_users,
                "banned_users": banned_users,
                "revenue_trend_pct": revenue_trend_pct,
                "orders_trend_pct": orders_trend_pct,
            },
            "orders_by_status": [
                {"status": row.status, "count": row.count}
                for row in sorted(status_agg, key=lambda row: row.status or "")
            ],
            "revenue_by_status": [
                {"status": row.status, "revenue": round(float(row.revenue or 0), 2)}
                for row in sorted(status_agg, key=lambda row: row.status or "")
            ],
            "top_products": [
                {
                    "product_id": row.product_id,
                    "name": row.name,
                    "quantity_sold": row.quantity_sold,
                    "revenue": round(float(row.revenue), 2),
                }
                for row in product_agg
            ],
            "monthly_growth": [
                {"month": row.month, "signups": row.count}
                for row in monthly_growth
            ],
            "recent_orders": [
                {
                    "order_id": o.id,
                    "order_number": o.id[:8],
                    "status": o.status,
                    "total": round(float(o.total or 0), 2),
                    "created_at": o.created_at,
                }
                for o in recent_orders
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
async def revenue_analytics(request: Request, _=Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    """Get revenue analytics (total and by status)"""
    try:
        status_result = await db.execute(
            select(Order.status, func.count().label("count"), func.sum(Order.total).label("revenue"))
            .group_by(Order.status).order_by(func.sum(Order.total).desc())
        )
        status_revenue = status_result.all()

        # Same "excludes cancelled" semantic as legacy_stats/dashboard_summary — see NOTES_schema_audit.md §9.
        total_revenue = (await db.execute(
            select(func.coalesce(func.sum(Order.total), 0)).where(Order.status != "cancelled")
        )).scalar_one()

        top_result = await db.execute(
            select(
                OrderItem.product_id,
                func.any_value(OrderItem.name).label("name"),
                func.sum(OrderItem.quantity).label("quantity"),
                func.sum(OrderItem.quantity * OrderItem.price).label("revenue"),
            )
            .group_by(OrderItem.product_id).order_by(func.sum(OrderItem.quantity * OrderItem.price).desc()).limit(5)
        )
        top_products = top_result.all()

        return {
            "total_revenue": round(total_revenue, 2),
            "by_status": [
                {"status": s.status, "count": s.count, "revenue": round(s.revenue or 0, 2)}
                for s in status_revenue
            ],
            "top_products": [
                {"product_id": p.product_id, "name": p.name, "quantity_sold": p.quantity, "revenue": round(p.revenue, 2)}
                for p in top_products
            ]
        }
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Revenue analytics error: {e}", {"endpoint": "revenue_analytics"})
        logger.error(f"Revenue analytics error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch revenue analytics")

@router.get("/analytics/orders")
@limiter.limit("30/minute")
async def order_analytics(request: Request, _=Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    """Get order analytics by status"""
    try:
        result = await db.execute(select(Order.status, func.count().label("count")).group_by(Order.status))
        status_map = {row.status: row.count for row in result.all()}

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
async def user_analytics(request: Request, _=Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    """Get user analytics (growth, active users)"""
    try:
        total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
        active_users = (await db.execute(select(func.count()).select_from(User).where(User.is_active == True))).scalar_one()  # noqa: E712
        banned_users = (await db.execute(select(func.count()).select_from(User).where(User.is_banned == True))).scalar_one()  # noqa: E712

        month_bucket = func.date_format(User.created_at, "%Y-%m")
        result = await db.execute(
            select(month_bucket.label("month"), func.count().label("count"))
            .group_by(month_bucket).order_by(month_bucket).limit(12)
        )
        monthly_growth = result.all()

        return {
            "total_users": total_users,
            "active_users": active_users,
            "banned_users": banned_users,
            "inactive_users": total_users - active_users,
            "monthly_growth": [
                {"month": row.month, "signups": row.count}
                for row in monthly_growth
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
@limiter.limit(settings.rate_login)
async def login(credentials: AdminLogin, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Admin login.

    Refresh token contract matches the customer flow (routes/auth.py): httpOnly cookie, never
    exposed to JS, rather than the old admin-only pattern of returning it in the JSON body for
    localStorage storage (which was reachable by any XSS on the page). A distinct cookie name
    ("admin_refresh_token" vs "refresh_token") avoids the two sessions clobbering each other when
    both the admin panel and customer site are open in the same browser on the same origin. See
    NOTES_schema_audit.md §7.

    Rate limited per-IP (slowapi), on top of AdminAuthService.authenticate's separate per-account
    failed-attempt counter — the two are deliberately independent: the per-IP limit throttles an
    attacker hammering many admin emails from one machine, while the per-account counter protects
    a single targeted admin even if the attacker rotates IPs.
    """
    try:
        result = await AdminAuthService.authenticate(
            db,
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
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Refresh access token using the httpOnly refresh cookie set at login."""
    refresh_token_str = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token_str:
        raise HTTPException(status_code=401, detail="No refresh token")

    verify_csrf(request, CSRF_COOKIE_NAME)

    try:
        result = await AdminAuthService.refresh_token(db, refresh_token_str)
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
async def logout(request: Request, response: Response, admin_data: dict = Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    """Admin logout.

    Computes the client IP directly rather than reading request.state.ip_address: that attribute
    is only set by AdminAuthMiddleware, which deliberately skips every /admin/auth/* path (so the
    unauthenticated login/refresh endpoints on that same prefix work) — meaning it was never set
    here, and this endpoint 500'd on every call. See NOTES_schema_audit.md.
    """
    try:
        # Revoke the refresh token's jti too (see utils/token_revocation.py) — otherwise a copy
        # captured before logout stays valid for the rest of its 7-day lifetime.
        refresh_token_str = request.cookies.get(REFRESH_COOKIE_NAME)
        if refresh_token_str:
            from jose import jwt, JWTError
            try:
                payload = jwt.decode(refresh_token_str, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
                if payload.get("type") == "refresh" and payload.get("jti") and payload.get("exp") is not None:
                    await revoke_jti(db, payload["jti"], payload.get("sub"), payload.get("role"), datetime.fromtimestamp(payload["exp"], tz=timezone.utc))
            except JWTError:
                pass  # already invalid/expired — nothing left to revoke

        await AdminAuthService.logout(
            admin_id=admin_data["admin_id"],
            ip_address=request.client.host if request.client else "0.0.0.0"
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Change admin password. Body, not query params — mirrors routes/auth.py's ChangePasswordRequest."""
    try:
        await AdminAuthService.change_password(
            db,
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
async def unlock_admin_account(admin_id: str, admin_data: dict = Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    """Unlock a locked admin account. Super-admin only — "admin:update" is reserved for
    super_admin in utils/permissions.py. AdminAuthService.unlock_account already existed but had
    no route calling it. See NOTES_schema_audit.md §7."""
    if not await check_permission(admin_data, "admin:update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        await AdminAuthService.unlock_account(db, admin_id=admin_id, super_admin_id=admin_data["admin_id"])
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

@router.post("/products/upload-image", response_model=ImageUploadResponse)
@limiter.limit("20/minute")
async def upload_product_image(
    request: Request,
    file: UploadFile = File(...),
    admin_data: dict = Depends(verify_admin_token),
):
    """Upload a product image (admin only) — validates type/size, generates a thumbnail, and
    stores to S3 (if configured) or local disk otherwise (services/image_storage.py). Returns
    both URLs to attach to a product's `images` list via POST/PUT /admin/products, which still
    just takes a list of URL strings — this only replaces how the admin gets one.

    Rate-limited tighter than the plain-JSON product routes below (which have none) since file
    uploads are a heavier, more abuse-prone surface (larger payloads, storage cost per call)."""
    if not await check_permission(admin_data, "product:create"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    url, thumbnail_url = await ImageStorageService.upload(
        file, str(request.base_url), content_length_header=request.headers.get("content-length"),
    )
    await log_to_db(
        "PRODUCT_IMAGE_UPLOADED", __name__, f"image uploaded by admin {admin_data.get('admin_id')}",
        {"admin_id": admin_data.get("admin_id"), "url": url},
    )
    return {"success": True, "data": {"url": url, "thumbnail_url": thumbnail_url}}


@router.get("/products/export")
@limiter.limit("10/minute")
async def export_products(request: Request, admin_data: dict = Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    """CSV export of the full product catalog, one row per (product, variant) — the same shape
    POST /admin/products/import expects back, so export -> edit in a spreadsheet -> re-import
    is a supported round trip."""
    if not await check_permission(admin_data, "product:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    csv_text = await export_products_csv(db)
    return Response(
        content=csv_text, media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="products.csv"'},
    )


@router.post("/products/import")
@limiter.limit("5/minute")
async def import_products(
    request: Request, file: UploadFile = File(...),
    admin_data: dict = Depends(verify_admin_token), db: AsyncSession = Depends(get_db),
):
    """Bulk create/update products from a CSV in the same shape GET /admin/products/export
    produces. Each product group gets its own SAVEPOINT (services/csv_io.py) so one bad row
    doesn't roll back the rows that already succeeded earlier in the file — the response always
    reports created/updated counts plus a per-row error list rather than all-or-nothing 500ing."""
    if not await check_permission(admin_data, "product:create"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    file_bytes = await file.read()
    result = await import_products_csv(db, file_bytes, admin_data.get("admin_id"))
    await cache_clear_prefix("products:list:")
    await cache_delete("products:categories")
    await log_to_db(
        "PRODUCTS_CSV_IMPORTED", __name__, f"product CSV imported by admin {admin_data.get('admin_id')}",
        {"admin_id": admin_data.get("admin_id"), "created": result["created"], "updated": result["updated"], "error_count": len(result["errors"])},
    )
    return {"success": True, "data": result}


@router.post("/products")
async def create_product(
    product: ProductCreate,
    request: Request,
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Create new product"""
    if not await check_permission(admin_data, "product:create"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        product_id = await ProductService.create_product(
            db,
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Get product details"""
    if not await check_permission(admin_data, "product:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        product = await ProductService.get_product(db, product_id)
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Update product"""
    if not await check_permission(admin_data, "product:update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        updates = product.model_dump(exclude_unset=True)
        if "variants" in updates:
            updates["variants"] = [v.model_dump() if hasattr(v, "model_dump") else v for v in updates["variants"]]

        updated = await ProductService.update_product(
            db,
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Delete (soft) product"""
    if not await check_permission(admin_data, "product:delete"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        await ProductService.delete_product(db, product_id, admin_data["admin_id"])
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """List products"""
    if not await check_permission(admin_data, "product:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        products, total = await ProductService.list_products(
            db,
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Get low stock items"""
    if not await check_permission(admin_data, "inventory:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        items = await ProductService.get_low_stock_items(db)
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Adjust stock for variant"""
    if not await check_permission(admin_data, "inventory:update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        reason = sanitize_input(reason, max_length=300)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        await InventoryService.adjust_stock(
            db,
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Get inventory history for product"""
    if not await check_permission(admin_data, "inventory:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        history = await InventoryService.get_inventory_history(db, product_id, limit)
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

# NOTE: export/bulk-status-update must be declared before GET/POST /orders/{order_id} below —
# FastAPI matches routes in declaration order, so a literal "/orders/export" would otherwise be
# swallowed by the {order_id} path parameter (with order_id="export") and 404 as "not found".

@router.get("/orders/export")
@limiter.limit("10/minute")
async def export_orders(request: Request, admin_data: dict = Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    """CSV export of every order — reuses OrderService.list_orders() rather than a fresh query."""
    if not await check_permission(admin_data, "order:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    csv_text = await export_orders_csv(db)
    return Response(
        content=csv_text, media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="orders.csv"'},
    )


@router.post("/orders/bulk-status-update")
@limiter.limit("5/minute")
async def bulk_update_order_status(
    request: Request, file: UploadFile = File(...),
    admin_data: dict = Depends(verify_admin_token), db: AsyncSession = Depends(get_db),
):
    """Bulk order-status update via CSV (order_id,status,note columns) — e.g. importing a
    fulfillment center's "these shipped today" export, instead of clicking through each order
    individually. Every row still goes through OrderService.update_order_status() (same
    transition validation + customer email as a single manual update) — see services/csv_io.py.
    Deliberately does NOT support bulk-*creating* orders from CSV: an admin fabricating orders
    wholesale isn't a real workflow and would bypass every checkout invariant (real stock
    decrement, real pricing, real payment)."""
    if not await check_permission(admin_data, "order:update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    file_bytes = await file.read()
    result = await bulk_update_order_status_csv(db, file_bytes, admin_data.get("admin_id"))
    await log_to_db(
        "ORDERS_BULK_STATUS_UPDATED", __name__, f"bulk order status update by admin {admin_data.get('admin_id')}",
        {"admin_id": admin_data.get("admin_id"), "updated": result["updated"], "error_count": len(result["errors"])},
    )
    return {"success": True, "data": result}


@router.get("/orders/{order_id}")
async def get_order(
    order_id: str,
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Get order details"""
    if not await check_permission(admin_data, "order:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        order = await OrderService.get_order(db, order_id)
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Update order status"""
    if not await check_permission(admin_data, "order:update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        order = await OrderService.update_order_status(
            db,
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """List orders"""
    if not await check_permission(admin_data, "order:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        orders, total = await OrderService.list_orders(
            db,
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Add note to order"""
    if not await check_permission(admin_data, "order:update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        note = sanitize_input(note, max_length=1000)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        order = await OrderService.add_order_note(
            db,
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
# RETURNS / REFUNDS QUEUE (pairs with the customer-facing POST /orders/{id}/return-request)
# ════════════════════════════════════════════════════════════════════════════

@router.get("/returns", response_model=ReturnRequestListResponse)
@limiter.limit("30/minute")
async def list_return_requests(
    request: Request,
    status: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """List return requests — same "order:read" permission as the order list, since a return
    request is order-adjacent (support can view; only admin/manager+ can resolve, see below)."""
    if not await check_permission(admin_data, "order:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    query = select(ReturnRequest)
    count_query = select(func.count()).select_from(ReturnRequest)
    if status:
        query = query.where(ReturnRequest.status == status)
        count_query = count_query.where(ReturnRequest.status == status)
    query = query.order_by(ReturnRequest.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    requests = result.scalars().all()
    total = (await db.execute(count_query)).scalar_one()
    return {
        "data": [_return_request_to_dict(r) for r in requests],
        "total": total, "page": (skip // limit) + 1 if limit else 1, "pages": -(-total // limit) if limit else 1,
    }


@router.patch("/returns/{return_id}", response_model=ReturnRequestResponse)
@limiter.limit("20/minute")
async def resolve_return_request_route(
    request: Request, return_id: str, body: ReturnRequestResolve,
    admin_data: dict = Depends(verify_admin_token), db: AsyncSession = Depends(get_db),
):
    """Approve or reject a return request. Approving transitions the order delivered -> returned
    (utils/order_transitions.py already allows this), restores the returned items' stock, and
    emails the customer either way — see services/return_request.py::resolve_return_request."""
    if not await check_permission(admin_data, "order:update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if not is_valid_id(return_id):
        raise HTTPException(status_code=400, detail="Invalid return request ID")

    rr = await db.get(ReturnRequest, return_id)
    if not rr:
        raise HTTPException(status_code=404, detail="Return request not found")

    result = await resolve_return_request(
        db, rr, body.action.value, admin_data["admin_id"], body.admin_note, body.refund_amount,
    )

    await AdminAuditService.log_action(
        admin_id=admin_data["admin_id"], admin_name=admin_data.get("name", "System"),
        action=f"return_request_{body.action.value}", entity_type="return_request", entity_id=return_id,
        changes={"status": {"old": "pending", "new": result["status"]}}, ip_address="0.0.0.0",
    )
    return result

# ════════════════════════════════════════════════════════════════════════════
# USER MANAGEMENT ROUTES
# ════════════════════════════════════════════════════════════════════════════

@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Get user details"""
    if not await check_permission(admin_data, "user:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        user = await UserService.get_user(db, user_id)
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """List users"""
    if not await check_permission(admin_data, "user:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        users, total = await UserService.list_users(
            db,
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Ban user"""
    if not await check_permission(admin_data, "user:ban"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        reason = sanitize_input(reason, max_length=300)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        user = await UserService.ban_user(
            db,
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Unban user"""
    if not await check_permission(admin_data, "user:ban"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        user = await UserService.unban_user(
            db,
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Get user's order history"""
    if not await check_permission(admin_data, "user:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        orders = await UserService.get_user_order_history(db, user_id, limit)
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
async def create_rider(rider: RiderCreate, admin_data: dict = Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    """Create a new rider account"""
    if not await check_permission(admin_data, "rider:create"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        created = await RiderService.create_rider(
            db,
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
async def list_riders(is_active: Optional[bool] = None, admin_data: dict = Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    """List riders with their live status/availability"""
    if not await check_permission(admin_data, "rider:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        riders = await RiderService.list_riders(db, is_active=is_active)
        return {"success": True, "data": riders, "total": len(riders)}
    except Exception as e:
        logger.error(f"List riders error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch riders")

@router.get("/riders/{rider_id}/active-orders")
async def get_rider_active_orders(rider_id: str, admin_data: dict = Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    """Count of a rider's currently active (not delivered/cancelled) orders"""
    if not await check_permission(admin_data, "rider:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        count = await RiderService.get_active_order_count(db, rider_id)
        return {"success": True, "data": {"rider_id": rider_id, "active_orders": count}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rider active-orders error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch rider's active orders")

@router.patch("/riders/{rider_id}/activate")
async def activate_rider(rider_id: str, admin_data: dict = Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    """Activate a rider account"""
    if not await check_permission(admin_data, "rider:update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        updated = await RiderService.set_active(db, rider_id, True, admin_data["admin_id"])
        return {"success": True, "message": "Rider activated", "data": updated}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Activate rider error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to activate rider")

@router.patch("/riders/{rider_id}/deactivate")
async def deactivate_rider(rider_id: str, admin_data: dict = Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    """Deactivate a rider account"""
    if not await check_permission(admin_data, "rider:update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        updated = await RiderService.set_active(db, rider_id, False, admin_data["admin_id"])
        return {"success": True, "message": "Rider deactivated", "data": updated}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Deactivate rider error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to deactivate rider")

@router.patch("/orders/{order_id}/assign-rider")
async def assign_rider(order_id: str, rider_id: str, admin_data: dict = Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    """Assign a rider to an order (admin only).

    Canonical assign-rider path — validates the rider exists and is active/available, and that
    the order isn't already delivered/cancelled, before assigning. Replaces the old
    routes/orders.py::assign_rider, which had neither check and was gated by the customer-facing
    JWT auth path instead of the admin permission matrix. See NOTES_schema_audit.md §4.
    """
    if not await check_permission(admin_data, "order:update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if not is_valid_id(order_id):
        raise HTTPException(status_code=400, detail="Invalid order ID")

    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status in ("delivered", "cancelled", "returned"):
        raise HTTPException(status_code=400, detail=f"Cannot assign a rider to a {order.status} order")

    if not await RiderService.is_available_for_assignment(db, rider_id):
        raise HTTPException(status_code=400, detail="Rider does not exist or is not active/available")

    order.rider_id = rider_id
    order.updated_at = datetime.now(timezone.utc)
    return {"success": True, "message": "Rider assigned"}

# ════════════════════════════════════════════════════════════════════════════
# DISCOUNT ROUTES
# ════════════════════════════════════════════════════════════════════════════

@router.post("/discounts")
async def create_discount(
    discount: DiscountCreate,
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Create new discount"""
    if not await check_permission(admin_data, "promo:create"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        discount_id = await DiscountService.create_discount(
            db,
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Get discount details"""
    if not await check_permission(admin_data, "promo:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        discount = await DiscountService.get_discount(db, discount_id)
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Update discount"""
    if not await check_permission(admin_data, "promo:update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        updates = update.model_dump(exclude_unset=True)
        discount = await DiscountService.update_discount(
            db,
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """List discounts"""
    if not await check_permission(admin_data, "promo:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        discounts, total = await DiscountService.list_discounts(
            db,
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard statistics"""
    if not await check_permission(admin_data, "dashboard:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        stats = await DashboardService.get_dashboard_stats(db)
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Get revenue trend"""
    if not await check_permission(admin_data, "dashboard:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        trend = await DashboardService.get_revenue_trend(db, days)
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Get top selling products"""
    if not await check_permission(admin_data, "dashboard:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        products = await DashboardService.get_top_products(db, limit)
        return {
            "success": True,
            "data": products
        }
    except Exception as e:
        logger.error(f"Get top products error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch top products")

@router.get("/dashboard/low-stock")
async def get_low_stock_dashboard(
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Get low stock items for dashboard"""
    if not await check_permission(admin_data, "dashboard:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        items = await DashboardService.get_low_stock_items(db)
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
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Get recent orders for dashboard"""
    if not await check_permission(admin_data, "dashboard:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        orders = await DashboardService.get_recent_orders(db, limit)
        return {
            "success": True,
            "data": orders,
            "count": len(orders)
        }
    except Exception as e:
        logger.error(f"Get recent orders error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch recent orders")


@router.get("/reports/sales-inventory")
@limiter.limit("10/minute")
async def download_sales_inventory_report(request: Request, admin_data: dict = Depends(verify_admin_token), db: AsyncSession = Depends(get_db)):
    """Downloadable Excel workbook (Summary / Revenue Trend / Top Products / Low Stock sheets)
    built entirely from services/dashboard.py's existing aggregation methods (services/reports.py)
    — the same numbers already shown on the dashboard, just exportable."""
    if not await check_permission(admin_data, "dashboard:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    xlsx_bytes = await generate_sales_inventory_report(db)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="sales-inventory-report.xlsx"'},
    )

# ════════════════════════════════════════════════════════════════════════════
# AUDIT LOG ROUTES
# ════════════════════════════════════════════════════════════════════════════

@router.get("/audit-logs")
async def get_audit_logs(
    entity_type: Optional[str] = None,
    admin_id: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    admin_data: dict = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
):
    """Get audit logs"""
    if not await check_permission(admin_data, "audit:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        logs, total = await AdminAuditService.get_logs(
            db,
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
