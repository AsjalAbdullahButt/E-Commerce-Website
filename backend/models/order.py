from pydantic import BaseModel
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
