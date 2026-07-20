from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict


class OrderItemResponse(BaseModel):
    product_id: str
    name: str
    price: float
    quantity: int
    size: Optional[str] = None
    color: Optional[str] = None
    image: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ShippingAddressResponse(BaseModel):
    full_name: str
    phone: str
    address: str
    city: str
    postal_code: str

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: str
    user_id: Optional[str] = None  # None for a guest order — see guest_email instead
    guest_email: Optional[str] = None
    items: List[OrderItemResponse]
    shipping_address: ShippingAddressResponse
    payment_method: str
    payment_reference: Optional[str] = None
    payment_status: str = "not_required"
    promo_code: Optional[str] = None
    subtotal: float = 0.0
    discount: float = 0.0
    tax: float = 0.0
    delivery_fee: float = 0.0
    total: float = 0.0
    status: str
    rider_id: Optional[str] = None
    rider_name: Optional[str] = None
    proof_of_delivery_url: Optional[str] = None
    status_history: List[dict[str, Any]] = []
    return_request: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class OrderListResponse(BaseModel):
    data: List[OrderResponse]
    total: int
    page: int
    pages: int
