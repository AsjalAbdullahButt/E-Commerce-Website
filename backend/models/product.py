from pydantic import BaseModel, field_validator
from typing import List, Optional

class ColorOption(BaseModel):
    name: str
    hex: str

class ProductCreate(BaseModel):
    name: str
    price: float
    description: str
    category: str = "t-shirts"
    images: List[str] = []
    sizes: List[str] = []
    colors: List[ColorOption] = []
    stock: int = 0

    @field_validator('price')
    @classmethod
    def price_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Price must be greater than 0')
        if v > 1_000_000:
            raise ValueError('Price seems unrealistically high')
        return round(v, 2)

    @field_validator('stock')
    @classmethod
    def stock_non_negative(cls, v):
        if v < 0:
            raise ValueError('Stock cannot be negative')
        return v

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    category: Optional[str] = None
    images: Optional[List[str]] = None
    sizes: Optional[List[str]] = None
    colors: Optional[List[ColorOption]] = None
    stock: Optional[int] = None
    is_active: Optional[bool] = None
