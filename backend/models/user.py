from pydantic import BaseModel, EmailStr
from typing import Optional
from enum import Enum

class UserRole(str, Enum):
    customer = "customer"
    admin    = "admin"
    rider    = "rider"

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: UserRole
    phone: Optional[str] = None
    address: Optional[str] = None
