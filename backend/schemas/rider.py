from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional


class RiderCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: str

    @field_validator('password')
    @classmethod
    def password_must_be_strong(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain digit')
        return v


class RiderProfileUpdate(BaseModel):
    """Body for the rider's own PATCH /rider/profile — JSON body, not query params."""
    name: Optional[str] = None
    phone: Optional[str] = None
