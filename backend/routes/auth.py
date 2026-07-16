from fastapi import APIRouter, HTTPException, Depends, Request, Response
from database import users_col, admin_users_col, riders_col
from models.user import UserCreate, UserLogin, UserUpdate
from utils.helpers import hash_password, verify_password, create_access_token, create_refresh_token, sanitize_input
from middleware.auth_middleware import get_current_user
from utils.limiter import limiter
from utils.logger import get_logger, log_to_db
from config import settings
from datetime import datetime, timedelta
from bson import ObjectId
from pydantic import BaseModel, EmailStr
import hashlib
import re
import secrets

logger = get_logger(__name__)

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
    refresh_token = create_refresh_token(str(result.inserted_id), "customer")

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
    if user and verify_password(body.password, user.get("password")):
        # Check active / banned flags
        if not user.get("is_active", True):
            raise HTTPException(status_code=403, detail="Account is deactivated")
        if user.get("is_banned"):
            raise HTTPException(status_code=403, detail="Account is banned")

        access_token = create_access_token(str(user["_id"]), user.get("role", "customer"))
        refresh_token = create_refresh_token(str(user["_id"]), user.get("role", "customer"))

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=settings.cookie_secure,
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
    admin_password = None
    if admin:
        admin_password = admin.get("password") or admin.get("password_hash")

    if admin and admin_password and verify_password(body.password, admin_password):
        # Check admin flags
        if not admin.get("is_active", True) or admin.get("is_locked"):
            raise HTTPException(status_code=403, detail="Account is deactivated or locked")
        access_token = create_access_token(str(admin["_id"]), "admin")
        refresh_token = create_refresh_token(str(admin["_id"]), "admin")

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=settings.cookie_secure,
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
    if rider and verify_password(body.password, rider.get("password")):
        # Check rider flags
        if not rider.get("is_active", True):
            raise HTTPException(status_code=403, detail="Account is deactivated")
        if rider.get("is_banned"):
            raise HTTPException(status_code=403, detail="Account is banned")
        access_token = create_access_token(str(rider["_id"]), "rider")
        refresh_token = create_refresh_token(str(rider["_id"]), "rider")

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=settings.cookie_secure,
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
        new_refresh_token = create_refresh_token(user_id, role)
        
        # Update refresh token cookie
        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="strict",
            max_age=7*24*60*60
        )
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
    except JWTError as e:
        await log_to_db("JWT_DECODE_ERROR", "refresh token validation failed", {"error": str(e)})
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

@router.post("/logout")
@limiter.limit("10/minute")
async def logout(request: Request, response: Response, user=Depends(get_current_user)):
    """Logout by clearing refresh token cookie"""
    response.delete_cookie("refresh_token", httponly=True, secure=settings.cookie_secure, samesite="strict")
    return {"message": "Logged out successfully"}

@router.get("/me")
@limiter.limit("60/minute")
async def me(request: Request, user=Depends(get_current_user)):
    """Get current authenticated user."""
    return serialize_user(user)

@router.put("/profile")
@limiter.limit("20/minute")
async def update_profile(request: Request, body: UserUpdate, user=Depends(get_current_user)):
    """Update user profile (name, phone, address). Customers only."""
    if user["role"] != "customer":
        raise HTTPException(status_code=403, detail="Only customers can update their profile")
    
    updates = {}
    if body.name:
        updates["name"] = sanitize_input(body.name)
    if body.phone:
        updates["phone"] = sanitize_input(body.phone)
    if body.address:
        updates["address"] = sanitize_input(body.address)
    
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    try:
        await users_col.update_one(
            {"_id": ObjectId(user["_id"])},
            {"$set": updates}
        )
        updated_user = await users_col.find_one({"_id": ObjectId(user["_id"])})
        await log_to_db("PROFILE_UPDATE", f"user {str(user['_id'])} updated profile", {"user_id": str(user["_id"]), "fields": list(updates.keys())})
        return {
            "success": True,
            "message": "Profile updated successfully",
            "user": serialize_user(updated_user)
        }
    except Exception as e:
        await log_to_db("PROFILE_UPDATE_ERROR", f"failed to update user profile", {"error": str(e), "user_id": str(user["_id"])})
        logger.error(f"Profile update error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update profile")

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/change-password")
@limiter.limit("5/minute")
async def change_password(request: Request, body: ChangePasswordRequest, user=Depends(get_current_user)):
    """Change user password. Passwords provided in request body, not query params."""
    try:
        # Fetch current user from appropriate collection
        role = user.get("role")
        uid = ObjectId(str(user.get("_id") or user.get("id")))
        current_user = None
        if role == "admin":
            current_user = await admin_users_col.find_one({"_id": uid})
        elif role == "rider":
            current_user = await riders_col.find_one({"_id": uid})
        else:
            current_user = await users_col.find_one({"_id": uid})

        if not current_user or not verify_password(body.old_password, current_user.get("password")):
            await log_to_db("PASSWORD_CHANGE_FAILED", "invalid old password", {"user_id": str(uid)})
            raise HTTPException(status_code=401, detail="Current password is incorrect")

        # Validate new password strength
        new_pw = body.new_password
        if len(new_pw) < 8 or not re.search(r"[A-Z]", new_pw) or not re.search(r"\d", new_pw):
            raise HTTPException(status_code=422, detail="New password must be at least 8 characters, include an uppercase letter and a digit")

        # Hash new password
        hashed = hash_password(new_pw)
        # Update in correct collection
        if role == "admin":
            await admin_users_col.update_one({"_id": uid}, {"$set": {"password": hashed, "updated_at": datetime.utcnow().isoformat()}})
        elif role == "rider":
            await riders_col.update_one({"_id": uid}, {"$set": {"password": hashed, "updated_at": datetime.utcnow().isoformat()}})
        else:
            await users_col.update_one({"_id": uid}, {"$set": {"password": hashed, "updated_at": datetime.utcnow().isoformat()}})

        await log_to_db("PASSWORD_CHANGED", f"user {str(uid)} changed password", {"user_id": str(uid)})
        return {"success": True, "message": "Password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await log_to_db("PASSWORD_CHANGE_ERROR", "failed to change password", {"error": str(e), "user_id": str(user.get("_id") or user.get("id"))})
        logger.error(f"Password change error: {e}")
        raise HTTPException(status_code=500, detail="Failed to change password")

RESET_TOKEN_EXPIRE_MINUTES = 30


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(request: Request, body: ForgotPasswordRequest):
    """Request a password reset link. Customers only (admin/rider passwords are managed by an
    admin). Always returns the same generic message regardless of whether the email exists, to
    avoid leaking which emails are registered."""
    email = sanitize_input(body.email)
    user = await users_col.find_one({"email": email})

    if user:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)

        await users_col.update_one(
            {"_id": user["_id"]},
            {"$set": {"reset_token_hash": token_hash, "reset_token_expires": expires_at.isoformat()}},
        )

        reset_link = f"{settings.frontend_url}/auth/reset-password.html?token={raw_token}"
        # No SMTP/email provider is configured for this app — log the link instead of emailing
        # it, so the flow is still fully testable end-to-end. Wire up a real provider here
        # (e.g. SendGrid/SES) before relying on this in production.
        logger.info(f"[DEV] Password reset link for {email}: {reset_link}")
        await log_to_db("PASSWORD_RESET_REQUESTED", f"password reset requested for {email}", {
            "user_id": str(user["_id"]), "reset_link": reset_link,
        })

    return {"message": "If an account with that email exists, a password reset link has been sent."}


@router.post("/reset-password")
@limiter.limit("5/minute")
async def reset_password(request: Request, body: ResetPasswordRequest):
    """Complete a password reset with the token from /forgot-password. Single-use: the token
    fields are cleared on success, so replaying the same token fails."""
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    user = await users_col.find_one({"reset_token_hash": token_hash})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    expires_at = user.get("reset_token_expires")
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at)
        except Exception:
            expires_at = None
    if not expires_at or expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    new_pw = body.new_password
    if len(new_pw) < 8 or not re.search(r"[A-Z]", new_pw) or not re.search(r"\d", new_pw):
        raise HTTPException(status_code=422, detail="New password must be at least 8 characters, include an uppercase letter and a digit")

    await users_col.update_one(
        {"_id": user["_id"]},
        {
            "$set": {"password": hash_password(new_pw), "updated_at": datetime.utcnow().isoformat()},
            "$unset": {"reset_token_hash": "", "reset_token_expires": ""},
        },
    )
    await log_to_db("PASSWORD_RESET_COMPLETED", f"password reset completed for user {str(user['_id'])}", {"user_id": str(user["_id"])})
    return {"message": "Password reset successfully. You can now log in with your new password."}


@router.patch("/me")
@limiter.limit("10/minute")
async def update_me(request: Request, body: UserUpdate, user=Depends(get_current_user)):
    """Update own profile. Supports customers and riders. Admin profile edits are not allowed here."""
    update_data = {k: v for k, v in body.dict().items() if v is not None}
    if update_data:
        # Sanitize string fields
        if "name" in update_data:
            update_data["name"] = sanitize_input(update_data["name"])
        if "address" in update_data:
            update_data["address"] = sanitize_input(update_data["address"])
        update_data["updated_at"] = datetime.utcnow().isoformat()

        # Determine collection based on role
        role = user.get("role")
        uid = ObjectId(str(user.get("_id") or user.get("id")))
        if role == "admin":
            # Do not allow admin profile edits via this endpoint
            raise HTTPException(status_code=403, detail="Admins must use admin profile endpoints")
        elif role == "rider":
            await riders_col.update_one({"_id": uid}, {"$set": update_data})
            updated = await riders_col.find_one({"_id": uid})
        else:
            await users_col.update_one({"_id": uid}, {"$set": update_data})
            updated = await users_col.find_one({"_id": uid})
        return serialize_user(updated)
    # Nothing to update: return current user
    return serialize_user(user)
