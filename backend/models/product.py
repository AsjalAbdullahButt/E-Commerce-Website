from pydantic import BaseModel
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
