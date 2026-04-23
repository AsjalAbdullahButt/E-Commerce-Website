from fastapi import APIRouter, HTTPException, Depends, Request, Response
from database import users_col, admin_users_col, riders_col
from models.user import UserCreate, UserLogin, UserUpdate
from utils.helpers import hash_password, verify_password, create_access_token, create_refresh_token, sanitize_input
from middleware.auth_middleware import get_current_user
from utils.limiter import limiter
from datetime import datetime
from bson import ObjectId

router = APIRouter()

def serialize_user(u: dict) -> dict:
    return {
        "id":      str(u["_id"]),
        "name":    u["name"],
        "email":   u["email"],
        "role":    u["role"],
        "phone":   u.get("phone"),
        "address": u.get("address"),
    }

@router.post("/register")
@limiter.limit("3/minute")
async def register(request: Request, body: UserCreate):
    """Register a new customer. Rate limited: 3 per minute per IP."""
    # Sanitize inputs
    name = sanitize_input(body.name)
    email = sanitize_input(body.email)
    
    existing = await users_col.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    doc = {
        "name":       name,
        "email":      email,
        "password":   hash_password(body.password),
        "phone":      body.phone,
        "role":       "customer",
        "is_active":  True,
        "created_at": datetime.utcnow().isoformat(),
    }
    result = await users_col.insert_one(doc)
    user   = await users_col.find_one({"_id": result.inserted_id})
    
    access_token = create_access_token(str(result.inserted_id), "customer")
    refresh_token = create_refresh_token(str(result.inserted_id))

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": serialize_user(user)
    }

@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, body: UserLogin, response: Response):
    """Unified login endpoint for customer, admin, and rider. Rate limited: 5 per minute per IP."""
    email = sanitize_input(body.email)
    
    # Try to find user in customers first
    user = await users_col.find_one({"email": email})
    if user and verify_password(body.password, user["password"]):
        access_token = create_access_token(str(user["_id"]), user["role"])
        refresh_token = create_refresh_token(str(user["_id"]))
        
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=7*24*60*60
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": serialize_user(user)
        }
    
    # Try admin_users collection
    admin = await admin_users_col.find_one({"email": email})
    if admin and verify_password(body.password, admin["password"]):
        access_token = create_access_token(str(admin["_id"]), "admin")
        refresh_token = create_refresh_token(str(admin["_id"]))
        
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=7*24*60*60
        )
        
        admin_serialized = {
            "id": str(admin["_id"]),
            "name": admin.get("name", "Admin"),
            "email": admin["email"],
            "role": "admin",
        }
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": admin_serialized
        }
    
    # Try riders collection
    rider = await riders_col.find_one({"email": email})
    if rider and verify_password(body.password, rider["password"]):
        access_token = create_access_token(str(rider["_id"]), "rider")
        refresh_token = create_refresh_token(str(rider["_id"]))
        
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=7*24*60*60
        )
        
        rider_serialized = {
            "id": str(rider["_id"]),
            "name": rider.get("name", "Rider"),
            "email": rider["email"],
            "role": "rider",
        }
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": rider_serialized
        }
    
    # Constant-time comparison even on missing user
    raise HTTPException(status_code=401, detail="Invalid email or password")

@router.post("/refresh")
@limiter.limit("10/minute")
async def refresh(request: Request, response: Response):
    """Refresh access token using refresh token from cookie"""
    from jose import jwt, JWTError
    from config import settings
    
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    
    try:
        payload = jwt.decode(
            refresh_token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )
        
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        user_id = payload.get("sub")
        role = payload.get("role")
        
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
        
        new_access_token = create_access_token(user_id, role)
        new_refresh_token = create_refresh_token(user_id)
        
        # Update refresh token cookie
        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=7*24*60*60
        )
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

@router.post("/logout")
@limiter.limit("10/minute")
async def logout(request: Request, response: Response, user=Depends(get_current_user)):
    """Logout by clearing refresh token cookie"""
    response.delete_cookie("refresh_token", httponly=True, secure=True, samesite="strict")
    return {"message": "Logged out successfully"}

@router.get("/me")
@limiter.limit("60/minute")
async def me(request: Request, user=Depends(get_current_user)):
    """Get current authenticated user."""
    return serialize_user(user)

@router.patch("/me")
@limiter.limit("10/minute")
async def update_me(request: Request, body: UserUpdate, user=Depends(get_current_user)):
    """Update own profile."""
    update_data = {k: v for k, v in body.dict().items() if v is not None}
    if update_data:
        # Sanitize string fields
        if "name" in update_data:
            update_data["name"] = sanitize_input(update_data["name"])
        if "address" in update_data:
            update_data["address"] = sanitize_input(update_data["address"])
        
        await users_col.update_one({"_id": user["_id"]}, {"$set": update_data})
    updated = await users_col.find_one({"_id": user["_id"]})
    return serialize_user(updated)
