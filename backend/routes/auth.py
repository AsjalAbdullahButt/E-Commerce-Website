from fastapi import APIRouter, HTTPException, Depends, Request
from database import users_col
from models.user import UserCreate, UserLogin, UserOut, UserUpdate
from utils.helpers import hash_password, verify_password, create_access_token
from middleware.auth_middleware import get_current_user
from utils.limiter import limiter
from datetime import datetime
from bson import ObjectId

router = APIRouter()

def serialize_user(u):
    return {
        "id": str(u["_id"]),
        "name": u["name"],
        "email": u["email"],
        "role": u["role"],
        "phone": u.get("phone"),
        "address": u.get("address")
    }

@router.post("/register")
@limiter.limit("3/minute")
async def register(request: Request, body: UserCreate):
    """Register a new user"""
    existing = await users_col.find_one({"email": body.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    doc = {
        **body.dict(),
        "password": hash_password(body.password),
        "role": "customer",
        "created_at": datetime.utcnow().isoformat()
    }
    result = await users_col.insert_one(doc)
    user = await users_col.find_one({"_id": result.inserted_id})
    token = create_access_token(str(result.inserted_id), "customer")
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": serialize_user(user)
    }

@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, body: UserLogin):
    """Login user"""
    user = await users_col.find_one({"email": body.email})
    if not user or not verify_password(body.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_access_token(str(user["_id"]), user["role"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": serialize_user(user)
    }

@router.get("/me")
async def me(user=Depends(get_current_user)):
    """Get current user info"""
    return serialize_user(user)

@router.patch("/me")
async def update_me(body: UserUpdate, user=Depends(get_current_user)):
    """Update user profile"""
    update_data = {k: v for k, v in body.dict().items() if v is not None}
    if not update_data:
        return serialize_user(user)
    
    await users_col.update_one({"_id": user["_id"]}, {"$set": update_data})
    updated = await users_col.find_one({"_id": user["_id"]})
    return serialize_user(updated)
