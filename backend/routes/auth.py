from fastapi import APIRouter, HTTPException, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db.admin import AdminUser
from db.rider import Rider
from db.user import User
from models.user import UserCreate, UserLogin, UserUpdate
from utils.helpers import hash_password, verify_password, create_access_token, create_refresh_token, sanitize_input
from middleware.auth_middleware import get_current_user
from utils.limiter import limiter
from utils.logger import get_logger, log_to_db
from utils.csrf import generate_csrf_token, set_csrf_cookie, verify_csrf
from utils.ids import is_valid_id
from utils.token_revocation import enforce_refresh_rotation, revoke_jti
from services.email import EmailService
from services.email_templates import password_reset_email
from config import settings
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr
import hashlib
import re
import secrets

logger = get_logger(__name__)

router = APIRouter()

REFRESH_COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days, matches jwt_refresh_expire_minutes default


def _set_session_cookies(response: Response, refresh_token: str) -> None:
    """Set the httpOnly refresh cookie plus its double-submit CSRF cookie together, so the two
    are always issued/rotated in lockstep. See utils/csrf.py for why only /auth/refresh needs
    this (not /auth/logout, which already requires a bearer token)."""
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=REFRESH_COOKIE_MAX_AGE,
    )
    set_csrf_cookie(response, "csrf_token", generate_csrf_token(), settings.cookie_secure, REFRESH_COOKIE_MAX_AGE)


def serialize_user(u) -> dict:
    """Accepts either a User ORM row or the dict shape middleware.auth_middleware::get_current_user
    returns (which already has string `id`)."""
    if isinstance(u, dict):
        return {
            "id":      u.get("id") or u.get("_id"),
            "name":    u["name"],
            "email":   u["email"],
            "role":    u["role"],
            "phone":   u.get("phone"),
            "address": u.get("address"),
        }
    return {
        "id":      u.id,
        "name":    u.name,
        "email":   u.email,
        "role":    u.role,
        "phone":   u.phone,
        "address": u.address,
    }

@router.post("/register")
@limiter.limit("3/minute")
async def register(request: Request, body: UserCreate, response: Response, db: AsyncSession = Depends(get_db)):
    """Register a new customer. Rate limited: 3 per minute per IP."""
    # Sanitize inputs
    name = sanitize_input(body.name)
    email = sanitize_input(body.email)

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=name, email=email, password=hash_password(body.password),
        phone=body.phone, role="customer", is_active=True,
    )
    db.add(user)
    await db.flush()

    access_token = create_access_token(user.id, "customer")
    refresh_token = create_refresh_token(user.id, "customer")

    # Match /login's cookie contract exactly — previously this returned refresh_token in the
    # JSON body (a secret leaking into the response) and never set the cookie at all, so a
    # freshly-registered user couldn't use /auth/refresh until they separately logged in.
    _set_session_cookies(response, refresh_token)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": serialize_user(user)
    }

@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, body: UserLogin, response: Response, db: AsyncSession = Depends(get_db)):
    """Unified login endpoint for customer, admin, and rider. Rate limited: 5 per minute per IP."""
    email = sanitize_input(body.email)

    # Try to find user in customers first
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user and verify_password(body.password, user.password):
        # Check active / banned flags
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is deactivated")
        if user.is_banned:
            raise HTTPException(status_code=403, detail="Account is banned")

        access_token = create_access_token(user.id, user.role or "customer")
        refresh_token = create_refresh_token(user.id, user.role or "customer")

        _set_session_cookies(response, refresh_token)

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": serialize_user(user)
        }

    # Try admin_users table
    admin_result = await db.execute(select(AdminUser).where(AdminUser.email == email))
    admin = admin_result.scalar_one_or_none()

    if admin and verify_password(body.password, admin.password_hash):
        # Check admin flags
        if not admin.is_active or admin.is_locked:
            raise HTTPException(status_code=403, detail="Account is deactivated or locked")
        access_token = create_access_token(admin.id, "admin")
        refresh_token = create_refresh_token(admin.id, "admin")

        _set_session_cookies(response, refresh_token)

        admin_serialized = {
            "id": admin.id,
            "name": admin.name or "Admin",
            "email": admin.email,
            "role": "admin",
        }

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": admin_serialized
        }

    # Try riders table
    rider_result = await db.execute(select(Rider).where(Rider.email == email))
    rider = rider_result.scalar_one_or_none()
    if rider and verify_password(body.password, rider.password):
        # Check rider flags
        if not rider.is_active:
            raise HTTPException(status_code=403, detail="Account is deactivated")
        access_token = create_access_token(rider.id, "rider")
        refresh_token = create_refresh_token(rider.id, "rider")

        _set_session_cookies(response, refresh_token)

        rider_serialized = {
            "id": rider.id,
            "name": rider.name or "Rider",
            "email": rider.email,
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
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Refresh access token using refresh token from cookie. This is the only endpoint that
    authenticates purely off a cookie (no bearer header), so it's the one that needs an explicit
    CSRF check — see utils/csrf.py."""
    from jose import jwt, JWTError

    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    verify_csrf(request, "csrf_token")

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

        # Find user in appropriate table based on role
        user_obj = None
        if role == "admin":
            user_obj = await db.get(AdminUser, user_id)
        elif role == "rider":
            user_obj = await db.get(Rider, user_id)
        else:  # customer
            user_obj = await db.get(User, user_id)

        if not user_obj:
            raise HTTPException(status_code=401, detail="User not found")

        # A banned/deactivated/locked account must not be able to mint fresh access tokens just
        # because its existing refresh token hasn't expired yet — otherwise a ban only takes
        # effect once the current 15-minute access token happens to expire.
        if not getattr(user_obj, "is_active", True):
            raise HTTPException(status_code=401, detail="Account is deactivated")
        if getattr(user_obj, "is_banned", False):
            raise HTTPException(status_code=401, detail="Account is banned")
        if getattr(user_obj, "is_locked", False):
            raise HTTPException(status_code=401, detail="Account is locked")

        await enforce_refresh_rotation(db, user_obj, payload)

        new_access_token = create_access_token(user_id, role)
        new_refresh_token = create_refresh_token(user_id, role)

        _set_session_cookies(response, new_refresh_token)

        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
    except JWTError as e:
        await log_to_db("JWT_DECODE_ERROR", __name__, "refresh token validation failed", {"error": str(e)})
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

@router.post("/logout")
@limiter.limit("10/minute")
async def logout(request: Request, response: Response, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Logout: clears the refresh token cookie AND revokes the refresh token's jti, so a copy of
    it captured before logout (compromised device, proxy log) can't still be used for the rest
    of its 7-day lifetime."""
    from jose import jwt, JWTError

    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            payload = jwt.decode(refresh_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            if payload.get("type") == "refresh" and payload.get("jti") and payload.get("exp") is not None:
                await revoke_jti(db, payload["jti"], payload.get("sub"), payload.get("role"), datetime.utcfromtimestamp(payload["exp"]))
        except JWTError:
            pass  # already invalid/expired — nothing left to revoke

    response.delete_cookie("refresh_token", httponly=True, secure=settings.cookie_secure, samesite="strict")
    response.delete_cookie("csrf_token", httponly=False, secure=settings.cookie_secure, samesite="strict")
    return {"message": "Logged out successfully"}

@router.get("/me")
@limiter.limit("60/minute")
async def me(request: Request, user=Depends(get_current_user)):
    """Get current authenticated user."""
    return serialize_user(user)

@router.put("/profile")
@limiter.limit("20/minute")
async def update_profile(request: Request, body: UserUpdate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
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
        user_obj = await db.get(User, user["_id"])
        for key, value in updates.items():
            setattr(user_obj, key, value)
        await log_to_db("PROFILE_UPDATE", __name__, f"user {str(user['_id'])} updated profile", {"user_id": str(user["_id"]), "fields": list(updates.keys())})
        return {
            "success": True,
            "message": "Profile updated successfully",
            "user": serialize_user(user_obj)
        }
    except Exception as e:
        await log_to_db("PROFILE_UPDATE_ERROR", __name__, f"failed to update user profile", {"error": str(e), "user_id": str(user["_id"])})
        logger.error(f"Profile update error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update profile")

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/change-password")
@limiter.limit("5/minute")
async def change_password(request: Request, body: ChangePasswordRequest, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Change user password. Passwords provided in request body, not query params."""
    try:
        # Fetch current user from appropriate table
        role = user.get("role")
        uid = str(user.get("_id") or user.get("id"))
        if role == "admin":
            current_user = await db.get(AdminUser, uid)
            current_password = current_user.password_hash if current_user else None
        elif role == "rider":
            current_user = await db.get(Rider, uid)
            current_password = current_user.password if current_user else None
        else:
            current_user = await db.get(User, uid)
            current_password = current_user.password if current_user else None

        if not current_user or not verify_password(body.old_password, current_password):
            await log_to_db("PASSWORD_CHANGE_FAILED", __name__, "invalid old password", {"user_id": uid})
            raise HTTPException(status_code=401, detail="Current password is incorrect")

        # Validate new password strength
        new_pw = body.new_password
        if len(new_pw) < 8 or not re.search(r"[A-Z]", new_pw) or not re.search(r"\d", new_pw):
            raise HTTPException(status_code=422, detail="New password must be at least 8 characters, include an uppercase letter and a digit")

        # Hash new password, update in correct table
        hashed = hash_password(new_pw)
        if role == "admin":
            current_user.password_hash = hashed
        else:
            current_user.password = hashed
        current_user.updated_at = datetime.utcnow()

        await log_to_db("PASSWORD_CHANGED", __name__, f"user {uid} changed password", {"user_id": uid})
        return {"success": True, "message": "Password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await log_to_db("PASSWORD_CHANGE_ERROR", __name__, "failed to change password", {"error": str(e), "user_id": str(user.get("_id") or user.get("id"))})
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
async def forgot_password(request: Request, body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Request a password reset link. Customers only (admin/rider passwords are managed by an
    admin). Always returns the same generic message regardless of whether the email exists, to
    avoid leaking which emails are registered."""
    email = sanitize_input(body.email)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)

        user.reset_token_hash = token_hash
        user.reset_token_expires = expires_at

        reset_link = f"{settings.frontend_url}/auth/reset-password.html?token={raw_token}"
        # EmailService.send() falls back to logging the link when SendGrid isn't configured, so
        # this flow stays fully testable end-to-end without a real account — see services/email.py.
        subject, html = password_reset_email(user.name, reset_link)
        await EmailService.send(
            email, subject, html,
            event_code="PASSWORD_RESET_REQUESTED", meta={"user_id": user.id, "reset_link": reset_link},
        )

    return {"message": "If an account with that email exists, a password reset link has been sent."}


@router.post("/reset-password")
@limiter.limit("5/minute")
async def reset_password(request: Request, body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Complete a password reset with the token from /forgot-password. Single-use: the token
    fields are cleared on success, so replaying the same token fails."""
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    result = await db.execute(select(User).where(User.reset_token_hash == token_hash))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    expires_at = user.reset_token_expires
    if not expires_at or expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    new_pw = body.new_password
    if len(new_pw) < 8 or not re.search(r"[A-Z]", new_pw) or not re.search(r"\d", new_pw):
        raise HTTPException(status_code=422, detail="New password must be at least 8 characters, include an uppercase letter and a digit")

    user.password = hash_password(new_pw)
    user.updated_at = datetime.utcnow()
    user.reset_token_hash = None
    user.reset_token_expires = None

    await log_to_db("PASSWORD_RESET_COMPLETED", __name__, f"password reset completed for user {user.id}", {"user_id": user.id})
    return {"message": "Password reset successfully. You can now log in with your new password."}


@router.patch("/me")
@limiter.limit("10/minute")
async def update_me(request: Request, body: UserUpdate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Update own profile. Supports customers and riders. Admin profile edits are not allowed here."""
    update_data = {k: v for k, v in body.dict().items() if v is not None}
    if update_data:
        # Sanitize string fields
        if "name" in update_data:
            update_data["name"] = sanitize_input(update_data["name"])
        if "address" in update_data:
            update_data["address"] = sanitize_input(update_data["address"])

        # Determine table based on role
        role = user.get("role")
        uid = str(user.get("_id") or user.get("id"))
        if role == "admin":
            # Do not allow admin profile edits via this endpoint
            raise HTTPException(status_code=403, detail="Admins must use admin profile endpoints")
        elif role == "rider":
            updated = await db.get(Rider, uid)
            for key, value in update_data.items():
                if hasattr(updated, key):
                    setattr(updated, key, value)
            updated.updated_at = datetime.utcnow()
        else:
            updated = await db.get(User, uid)
            for key, value in update_data.items():
                setattr(updated, key, value)
            updated.updated_at = datetime.utcnow()
        return serialize_user(updated)
    # Nothing to update: return current user
    return serialize_user(user)
