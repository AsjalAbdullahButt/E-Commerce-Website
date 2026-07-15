from pydantic import BaseModel, field_validator
from typing import List, Optional
from enum import Enum

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

class OrderCreate(BaseModel):
    items: List[OrderItem]
    shipping_address: ShippingAddress
    promo_code: Optional[str] = None
    payment_method: Optional[str] = "cod"  # cod, jazzcash, easypaisa
    payment_reference: Optional[str] = None  # Transaction ID for mobile payments

class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    note: Optional[str] = None
