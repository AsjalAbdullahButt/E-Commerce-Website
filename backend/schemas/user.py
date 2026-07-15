from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None
    is_banned: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    data: List[UserResponse]
    total: int
    page: int
    pages: int


class UserDetailResponse(BaseModel):
    data: UserResponse
