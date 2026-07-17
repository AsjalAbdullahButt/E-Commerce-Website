from pydantic import BaseModel, EmailStr, field_validator
from typing import List, Optional
from enum import Enum
from utils.helpers import sanitize_input

class OrderStatus(str, Enum):
    pending   = "pending"
    confirmed = "confirmed"
    packed    = "packed"
    shipped   = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"

class OrderItem(BaseModel):
    product_id: str
    name: str
    price: float
    quantity: int
    size: str
    color: str
    image: str

    @field_validator('quantity')
    @classmethod
    def quantity_positive(cls, v):
        if v < 1 or v > 100:
            raise ValueError('Quantity must be between 1 and 100')
        return v

class ShippingAddress(BaseModel):
    full_name: str
    phone: str
    address: str
    city: str
    postal_code: str

    @field_validator('full_name')
    @classmethod
    def full_name_valid(cls, v):
        v = sanitize_input(v, max_length=100)
        if not v:
            raise ValueError('Full name cannot be empty')
        return v

    @field_validator('phone')
    @classmethod
    def phone_valid(cls, v):
        v = sanitize_input(v, max_length=20)
        if not v:
            raise ValueError('Phone cannot be empty')
        return v

    @field_validator('address')
    @classmethod
    def address_valid(cls, v):
        v = sanitize_input(v, max_length=300)
        if not v:
            raise ValueError('Address cannot be empty')
        return v

    @field_validator('city')
    @classmethod
    def city_valid(cls, v):
        v = sanitize_input(v, max_length=100)
        if not v:
            raise ValueError('City cannot be empty')
        return v

    @field_validator('postal_code')
    @classmethod
    def postal_code_valid(cls, v):
        return sanitize_input(v, max_length=20)

class OrderCreate(BaseModel):
    items: List[OrderItem]
    shipping_address: ShippingAddress
    promo_code: Optional[str] = None
    payment_method: Optional[str] = "cod"  # cod, jazzcash, easypaisa
    payment_reference: Optional[str] = None  # Transaction ID for mobile payments
    # Required only for guest checkout (no Authorization header) — routes/orders.py::place_order
    # rejects an unauthenticated request that omits this. Ignored for logged-in customers, whose
    # account email is used instead.
    guest_email: Optional[EmailStr] = None

class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    note: Optional[str] = None

    @field_validator('note')
    @classmethod
    def note_valid(cls, v):
        if v is None:
            return v
        return sanitize_input(v, max_length=500)
