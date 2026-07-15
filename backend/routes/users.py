from fastapi import APIRouter, Depends, Request, Query, HTTPException, status
from database import users_col
from middleware.auth_middleware import require_admin
from utils.limiter import limiter
from utils.logger import get_logger, log_to_db
from bson import ObjectId
from schemas.user import UserListResponse, UserDetailResponse

logger = get_logger(__name__)

router = APIRouter()


@router.get("", response_model=UserListResponse)
@limiter.limit("20/minute")
async def list_users(request: Request, page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=200), _=Depends(require_admin)):
    """List all users (admin only). Paginated."""
    skip = (page - 1) * limit
    cursor = users_col.find({}, {"password": 0, "password_hash": 0}).sort("created_at", -1).skip(skip).limit(limit)
    users = await cursor.to_list(length=limit)
    for u in users:
        u["id"] = str(u.pop("_id"))
        u.pop("password", None)
        u.pop("password_hash", None)
    total = await users_col.count_documents({})
    return {"data": users, "total": total, "page": page, "pages": -(-total // limit)}


@router.get("/{user_id}", response_model=UserDetailResponse)
@limiter.limit("20/minute")
async def get_user(request: Request, user_id: str, _=Depends(require_admin)):
    user = await users_col.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user["id"] = str(user.pop("_id"))
    user.pop("password", None)
    user.pop("password_hash", None)
    return {"data": user}


@router.patch("/{user_id}/ban")
@limiter.limit("10/minute")
async def ban_user(request: Request, user_id: str, _=Depends(require_admin)):
    res = await users_col.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_active": False, "is_banned": True}})
    if res.modified_count == 0:
        await log_to_db("USER_BAN_FAILED", f"admin attempted to ban non-existent user {user_id}", {"user_id": user_id})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or already banned")
    await log_to_db("USER_BANNED", f"user {user_id} was banned by admin", {"target_user_id": user_id})
    return {"success": True, "message": "User banned"}


@router.patch("/{user_id}/unban")
@limiter.limit("10/minute")
async def unban_user(request: Request, user_id: str, _=Depends(require_admin)):
    res = await users_col.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_active": True, "is_banned": False}})
    if res.modified_count == 0:
        await log_to_db("USER_UNBAN_FAILED", f"admin attempted to unban non-existent user {user_id}", {"user_id": user_id})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or already unbanned")
    await log_to_db("USER_UNBANNED", f"user {user_id} was unbanned by admin", {"target_user_id": user_id})
    return {"success": True, "message": "User unbanned"}


@router.delete("/{user_id}")
@limiter.limit("5/minute")
async def delete_user(request: Request, user_id: str, _=Depends(require_admin)):
    res = await users_col.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_deleted": True, "is_active": False}})
    if res.modified_count == 0:
        await log_to_db("USER_DELETE_FAILED", f"admin attempted to delete non-existent user {user_id}", {"user_id": user_id})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or already deleted")
    await log_to_db("USER_DELETED", f"user {user_id} was soft-deleted by admin", {"target_user_id": user_id})
    return {"success": True, "message": "User soft-deleted"}
