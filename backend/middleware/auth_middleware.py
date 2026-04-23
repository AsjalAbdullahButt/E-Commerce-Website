from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from bson import ObjectId
from config import settings
from database import users_col, admin_users_col, riders_col

security = HTTPBearer()

async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    """Extract and validate JWT token - works for all roles"""
    try:
        payload = jwt.decode(
            creds.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )
        user_id = payload.get("sub")
        role = payload.get("role")
        
        if not user_id or not role:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Find user in appropriate collection based on role
        user = None
        if role == "admin":
            user = await admin_users_col.find_one({"_id": ObjectId(user_id)})
        elif role == "rider":
            user = await riders_col.find_one({"_id": ObjectId(user_id)})
        else:  # customer
            user = await users_col.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        user["id"] = str(user["_id"])
        user["role"] = role  # Ensure role is set from JWT
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Token expired or invalid")

async def require_admin(user = Depends(get_current_user)):
    """Require admin role"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

async def require_rider(user = Depends(get_current_user)):
    """Require rider role"""
    if user.get("role") != "rider":
        raise HTTPException(status_code=403, detail="Rider access required")
    return user

async def require_customer(user = Depends(get_current_user)):
    """Require customer role"""
    if user.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Customer access required")
    return user
