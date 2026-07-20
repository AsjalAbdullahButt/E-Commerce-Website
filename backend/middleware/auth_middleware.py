from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from db.admin import AdminUser
from db.rider import Rider
from db.user import User

security = HTTPBearer()
_optional_security = HTTPBearer(auto_error=False)


def _row_to_dict(obj) -> dict:
    """ORM row -> plain dict, plus a Mongo-shaped `_id` alias (string, not ObjectId) so the many
    existing `str(user["_id"])` call sites across routes/services keep working unchanged."""
    data = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    data["_id"] = data["id"]
    return data


async def _resolve_user_from_token(token: str, db: AsyncSession) -> dict:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

    # A refresh token is only meant to mint new access tokens at /auth/refresh — without this
    # check, its 7-day lifetime (vs. 15 minutes for a real access token) let it authenticate
    # every customer/rider endpoint as if it were a short-lived access token.
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    role = payload.get("role")

    if not user_id or not role:
        raise HTTPException(status_code=401, detail="Invalid token")

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

    user = _row_to_dict(user_obj)
    user["role"] = role  # Ensure role is set from JWT

    # Ban/deactivation must take effect immediately, not just on the next login — otherwise a
    # banned customer/rider keeps working for up to 15 minutes on their current access token.
    # is_banned/is_locked don't exist on every role's table; dict.get() defaults to falsy for
    # whichever ones are absent (e.g. riders have no is_banned column).
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is deactivated")
    if user.get("is_banned"):
        raise HTTPException(status_code=403, detail="Account is banned")
    if user.get("is_locked"):
        raise HTTPException(status_code=403, detail="Account is locked")

    return user


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """Extract and validate JWT token - works for all roles"""
    try:
        return await _resolve_user_from_token(creds.credentials, db)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token expired or invalid")


async def get_current_user_optional(
    creds: HTTPAuthorizationCredentials = Depends(_optional_security),
    db: AsyncSession = Depends(get_db),
):
    """Same as get_current_user, but returns None instead of raising when no Authorization
    header is present at all — for endpoints that support both logged-in and guest callers
    (e.g. guest checkout, routes/orders.py::place_order). A header that IS present but invalid
    still raises 401 rather than silently downgrading to guest, so a stale/tampered token never
    masquerades as an intentional guest checkout."""
    if creds is None:
        return None
    try:
        return await _resolve_user_from_token(creds.credentials, db)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token expired or invalid")

async def require_admin(user = Depends(get_current_user)):
    """Require admin role"""
    ADMIN_ROLES = {"admin", "super_admin", "manager", "support"}
    if user.get("role") not in ADMIN_ROLES:
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
