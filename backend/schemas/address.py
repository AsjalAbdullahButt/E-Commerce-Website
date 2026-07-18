from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from utils.helpers import sanitize_input


class AddressCreate(BaseModel):
    label: Optional[str] = None
    full_name: str
    phone: str
    address: str
    city: str
    postal_code: str
    is_default: bool = False

    @field_validator("label")
    @classmethod
    def label_valid(cls, v):
        if v is None:
            return v
        return sanitize_input(v, max_length=50) or None

    @field_validator("full_name")
    @classmethod
    def full_name_valid(cls, v):
        v = sanitize_input(v, max_length=200)
        if not v:
            raise ValueError("Full name cannot be empty")
        return v

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v):
        v = sanitize_input(v, max_length=20)
        if not v:
            raise ValueError("Phone cannot be empty")
        return v

    @field_validator("address")
    @classmethod
    def address_valid(cls, v):
        v = sanitize_input(v, max_length=500)
        if not v:
            raise ValueError("Address cannot be empty")
        return v

    @field_validator("city")
    @classmethod
    def city_valid(cls, v):
        v = sanitize_input(v, max_length=100)
        if not v:
            raise ValueError("City cannot be empty")
        return v

    @field_validator("postal_code")
    @classmethod
    def postal_code_valid(cls, v):
        return sanitize_input(v, max_length=20)


class AddressUpdate(AddressCreate):
    pass


class AddressResponse(BaseModel):
    id: str
    label: Optional[str] = None
    full_name: str
    phone: str
    address: str
    city: str
    postal_code: str
    is_default: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
