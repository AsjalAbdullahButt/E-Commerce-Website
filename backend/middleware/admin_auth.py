from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from core.security import Security, has_permission
from database import admin_users_col
from bson import ObjectId
import logging

logger = logging.getLogger("admin_auth")

security = HTTPBearer()

async def verify_admin_token(credentials: HTTPAuthorizationCredentials) -> dict:
    """Verify admin JWT token"""
    try:
        token = credentials.credentials
        payload = Security.decode_token(token)
        
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        
        admin_id = payload.get("sub")
        if not admin_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        
        # Verify admin exists and is active
        admin = await admin_users_col.find_one(
            {"_id": ObjectId(admin_id), "is_active": True, "is_locked": False}
        )
        if not admin:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin not found or locked")
        
        return {
            "admin_id": str(admin["_id"]),
            "email": admin["email"],
            "name": admin["name"],
            "role": admin["role"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

async def check_permission(admin_data: dict, required_permission: str) -> bool:
    """Check if admin has required permission"""
    role = admin_data.get("role")
    return has_permission(role, required_permission)

class AdminAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to verify admin authentication on protected routes"""
    
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
            
            payload = Security.decode_token(credentials)
            if payload.get("type") != "access":
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"success": False, "message": "Invalid token type"}
                )
            
            admin_id = payload.get("sub")
            admin = await admin_users_col.find_one(
                {"_id": ObjectId(admin_id), "is_active": True, "is_locked": False}
            )
            if not admin:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"success": False, "message": "Admin not found or locked"}
                )
            
            # Attach admin data to request
            request.state.admin = {
                "admin_id": str(admin["_id"]),
                "email": admin["email"],
                "name": admin["name"],
                "role": admin["role"],
            }
            request.state.ip_address = request.client.host if request.client else "0.0.0.0"
            
        except Exception as e:
            logger.error(f"Auth middleware error: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"success": False, "message": "Authentication failed"}
            )
        
        return await call_next(request)
