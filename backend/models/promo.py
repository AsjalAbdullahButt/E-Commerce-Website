from pydantic import BaseModel
from typing import Optional
from enum import Enum
from datetime import datetime

class DiscountType(str, Enum):
    percentage = "percentage"
    fixed      = "fixed"

class PromoCreate(BaseModel):
    code: str
    discount_type: DiscountType
    discount_value: float
    min_order: float = 0
    max_uses: int = 100
    expires_at: Optional[datetime] = None

class PromoValidate(BaseModel):
    code: str
    order_total: float
