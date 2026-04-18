from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from bson import ObjectId
from config import settings
from database import users_col

security = HTTPBearer()

async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    """Extract and validate JWT token"""
    try:
        payload = jwt.decode(
            creds.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = await users_col.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        user["id"] = str(user["_id"])
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Token expired or invalid")

async def require_admin(user = Depends(get_current_user)):
    """Require admin role"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

async def require_rider(user = Depends(get_current_user)):
    """Require rider or admin role"""
    if user.get("role") not in ["admin", "rider"]:
        raise HTTPException(status_code=403, detail="Rider access required")
    return user
