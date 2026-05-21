from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
from typing import Optional, List
from enum import Enum
from datetime import datetime

# ════════════════════════════════════════════════════════════════════════════
# ENUMS
# ════════════════════════════════════════════════════════════════════════════

class AdminRole(str, Enum):
    super_admin = "super_admin"
    admin = "admin"
    manager = "manager"
    support = "support"

class OrderStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    packed = "packed"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"
    returned = "returned"

class PaymentMethod(str, Enum):
    cod = "cod"
    jazzcash = "jazzcash"
    easypaisa = "easypaisa"

class DiscountType(str, Enum):
    percentage = "percentage"
    fixed = "fixed"

# ════════════════════════════════════════════════════════════════════════════
# PRODUCT SCHEMAS
# ════════════════════════════════════════════════════════════════════════════

class ProductVariant(BaseModel):
    """Product variant: Size + Color"""
    size: str
    color: str
    sku: str  # Unique SKU per variant
    stock: int = 0
    model_config = ConfigDict(from_attributes=True)

class ProductVariantUpdate(BaseModel):
    size: Optional[str] = None
    color: Optional[str] = None
    sku: Optional[str] = None
    stock: Optional[int] = None

class ProductCreate(BaseModel):
    name: str
    description: str
    category: str
    price: float
    discount_percentage: float = 0.0
    variants: List[ProductVariant]
    tags: List[str] = []
    images: List[str] = []
    model_config = ConfigDict(from_attributes=True)

    @field_validator('price')
    @classmethod
    def price_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Price must be positive')
        return v

    @field_validator('discount_percentage')
    @classmethod
    def discount_valid(cls, v):
        if not 0 <= v <= 100:
            raise ValueError('Discount must be between 0 and 100')
        return v

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    discount_percentage: Optional[float] = None
    tags: Optional[List[str]] = None
    images: Optional[List[str]] = None
    variants: Optional[List[ProductVariantUpdate]] = None
    is_active: Optional[bool] = None

class ProductResponse(BaseModel):
    id: str
    name: str
    description: str
    category: str
    price: float
    discount_percentage: float
    variants: List[ProductVariant]
    tags: List[str]
    images: List[str]
    is_active: bool
    total_stock: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ════════════════════════════════════════════════════════════════════════════
# INVENTORY SCHEMAS
# ════════════════════════════════════════════════════════════════════════════

class InventoryLog(BaseModel):
    product_id: str
    variant_sku: str
    quantity_changed: int
    reason: str  # "order", "adjustment", "return", etc.
    admin_id: Optional[str] = None
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

class InventoryHistoryResponse(BaseModel):
    id: str
    logs: List[InventoryLog]
    model_config = ConfigDict(from_attributes=True)

# ════════════════════════════════════════════════════════════════════════════
# ORDER SCHEMAS
# ════════════════════════════════════════════════════════════════════════════

class OrderItemDetail(BaseModel):
    product_id: str
    product_name: str
    price: float
    quantity: int
    size: str
    color: str
    image: str
    model_config = ConfigDict(from_attributes=True)

class ShippingAddress(BaseModel):
    full_name: str
    phone: str
    address: str
    city: str
    postal_code: str
    model_config = ConfigDict(from_attributes=True)

class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    note: Optional[str] = None

class OrderResponse(BaseModel):
    id: str
    user_id: str
    user_email: str
    items: List[OrderItemDetail]
    shipping_address: ShippingAddress
    payment_method: PaymentMethod
    total_price: float
    discount_applied: float
    final_price: float
    status: OrderStatus
    timeline: List[dict]  # Status change history
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ════════════════════════════════════════════════════════════════════════════
# USER SCHEMAS
# ════════════════════════════════════════════════════════════════════════════

class AdminUserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: AdminRole

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

class AdminUserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[AdminRole] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

class AdminUserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: AdminRole
    is_active: bool
    failed_login_attempts: int
    is_locked: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class CustomerUserResponse(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str]
    is_banned: bool
    total_orders: int
    total_spent: float
    created_at: datetime
    last_login: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)

# ════════════════════════════════════════════════════════════════════════════
# DISCOUNT/COUPON SCHEMAS
# ════════════════════════════════════════════════════════════════════════════

class DiscountCreate(BaseModel):
    code: str
    description: str
    discount_type: DiscountType
    discount_value: float
    max_usage: int
    min_order_value: float = 0
    expiry_date: datetime

    @field_validator('discount_value')
    @classmethod
    def discount_value_valid(cls, v):
        if v <= 0:
            raise ValueError('Discount value must be positive')
        return v

class DiscountUpdate(BaseModel):
    description: Optional[str] = None
    max_usage: Optional[int] = None
    is_active: Optional[bool] = None
    expiry_date: Optional[datetime] = None

class DiscountResponse(BaseModel):
    id: str
    code: str
    description: str
    discount_type: DiscountType
    discount_value: float
    max_usage: int
    current_usage: int
    min_order_value: float
    is_active: bool
    expiry_date: datetime
    created_by: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ════════════════════════════════════════════════════════════════════════════
# AUDIT LOG SCHEMAS
# ════════════════════════════════════════════════════════════════════════════

class AuditLogResponse(BaseModel):
    id: str
    admin_id: str
    admin_name: str
    action: str
    entity_type: str
    entity_id: str
    changes: dict
    timestamp: datetime
    ip_address: str
    model_config = ConfigDict(from_attributes=True)

# ════════════════════════════════════════════════════════════════════════════
# AUTH SCHEMAS
# ════════════════════════════════════════════════════════════════════════════

class AdminLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

# ════════════════════════════════════════════════════════════════════════════
# DASHBOARD SCHEMAS
# ════════════════════════════════════════════════════════════════════════════

class DashboardStats(BaseModel):
    total_sales: float
    total_orders: int
    total_users: int
    low_stock_items: int
    pending_orders: int
    revenue_today: float
    orders_today: int
    model_config = ConfigDict(from_attributes=True)

class ChartData(BaseModel):
    labels: List[str]
    data: List[float]
    model_config = ConfigDict(from_attributes=True)

class DashboardResponse(BaseModel):
    stats: DashboardStats
    revenue_trend: ChartData
    top_products: List[dict]
    low_stock_items: List[dict]
    recent_orders: List[OrderResponse]
    model_config = ConfigDict(from_attributes=True)
