from pydantic import BaseModel, field_validator
from typing import List, Optional

class ProductVariant(BaseModel):
    size: str
    color: str
    sku: str
    stock: int = 0

    @field_validator('stock')
    @classmethod
    def stock_non_negative(cls, v):
        if v < 0:
            raise ValueError('Stock cannot be negative')
        return v

class ProductVariantUpdate(BaseModel):
    size: Optional[str] = None
    color: Optional[str] = None
    sku: Optional[str] = None
    stock: Optional[int] = None

class ProductCreate(BaseModel):
    name: str
    price: float
    description: str
    category: str = "t-shirts"
    images: List[str] = []
    discount_percentage: float = 0.0
    tags: List[str] = []
    variants: List[ProductVariant] = []

    @field_validator('price')
    @classmethod
    def price_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Price must be greater than 0')
        if v > 1_000_000:
            raise ValueError('Price seems unrealistically high')
        return round(v, 2)

    @field_validator('discount_percentage')
    @classmethod
    def discount_valid(cls, v):
        if not 0 <= v <= 100:
            raise ValueError('Discount must be between 0 and 100')
        return v

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    category: Optional[str] = None
    images: Optional[List[str]] = None
    discount_percentage: Optional[float] = None
    tags: Optional[List[str]] = None
    variants: Optional[List[ProductVariant]] = None
    is_active: Optional[bool] = None
