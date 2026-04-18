from fastapi import APIRouter, Depends
from database import users_col
from middleware.auth_middleware import require_admin

router = APIRouter()

@router.get("")
async def list_users(_=Depends(require_admin)):
    """List all users (admin only)"""
    users = await users_col.find({}, {"password": 0}).to_list(length=500)
    for u in users:
        u["id"] = str(u.pop("_id"))
    return users
