from fastapi import Depends, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from database import AsyncSessionLocal, get_db
from db.admin import AdminUser
from sqlalchemy.ext.asyncio import AsyncSession
from utils.helpers import decode_token
from utils.logger import get_logger, log_to_db
from utils.permissions import has_permission

logger = get_logger(__name__)


def _admin_to_dict(admin: AdminUser) -> dict:
    return {
        "admin_id": admin.id,
        "email": admin.email,
        "name": admin.name,
        "role": admin.role,
    }


async def verify_admin_token(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Verify admin JWT token.

    Prefer the admin object attached by AdminAuthMiddleware to avoid a second DB lookup.
    """
    try:
        admin_state = getattr(request.state, "admin", None)
        if admin_state:
            return admin_state

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization header")

        scheme, token = auth_header.split(" ")
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization scheme")

        payload = decode_token(token)

        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

        admin_id = payload.get("sub")
        if not admin_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        # Verify admin exists and is active
        admin = await db.get(AdminUser, admin_id)
        if not admin or not admin.is_active or admin.is_locked:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin not found or locked")

        return _admin_to_dict(admin)
    except HTTPException:
        raise
    except Exception as e:
        await log_to_db("ERROR", __name__, f"Token verification error: {e}")
        logger.error(f"Token verification error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

async def check_permission(admin_data: dict, required_permission: str) -> bool:
    """Check if admin has required permission"""
    role = admin_data.get("role")
    return has_permission(role, required_permission)

class AdminAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to verify admin authentication on protected routes.

    Runs as raw ASGI middleware, outside FastAPI's Depends system, so it can't receive a
    request-scoped session via Depends(get_db) — it opens its own short-lived session instead,
    same pattern as utils/logger.py::log_to_db.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Apply this middleware only to admin routes.
        if not path.startswith("/admin"):
            return await call_next(request)

        # Skip auth for public endpoints
        public_paths = ["/docs", "/openapi.json", "/health"]
        if any(request.url.path.startswith(p) for p in public_paths):
            return await call_next(request)

        if path.startswith("/admin/auth"):  # Skip admin auth endpoints
            return await call_next(request)

        # Check for authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"success": False, "message": "Missing authorization header"}
            )

        try:
            scheme, credentials = auth_header.split(" ")
            if scheme.lower() != "bearer":
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"success": False, "message": "Invalid authorization scheme"}
                )

            payload = decode_token(credentials)
            if payload.get("type") != "access":
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"success": False, "message": "Invalid token type"}
                )

            admin_id = payload.get("sub")
            async with AsyncSessionLocal() as session:
                admin = await session.get(AdminUser, admin_id)

            if not admin or not admin.is_active or admin.is_locked:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"success": False, "message": "Admin not found or locked"}
                )

            # Attach admin data to request
            request.state.admin = _admin_to_dict(admin)
            request.state.ip_address = request.client.host if request.client else "0.0.0.0"

        except Exception as e:
            await log_to_db("ERROR", __name__, f"Auth middleware error: {e}", {"path": path})
            logger.error(f"Auth middleware error: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"success": False, "message": "Authentication failed"}
            )

        return await call_next(request)
