from fastapi import APIRouter, Depends, Request
from database import users_col
from middleware.auth_middleware import require_admin
from utils.limiter import limiter

router = APIRouter()

@router.get("")
@limiter.limit("20/minute")
async def list_users(request: Request, _=Depends(require_admin)):
    """List all users (admin only). Passwords excluded."""
    users = await users_col.find({}, {"password": 0}).to_list(length=500)
    for u in users:
        u["id"] = str(u.pop("_id"))
    return users
