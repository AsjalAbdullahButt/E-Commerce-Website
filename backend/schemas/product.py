from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict


class ProductResponse(BaseModel):
    id: str
    name: str
    description: str
    category: str
    price: float
    discount_percentage: float = 0.0
    variants: List[dict[str, Any]] = []
    tags: List[str] = []
    images: List[str] = []
    is_active: bool = True
    total_stock: int = 0
    rating: float = 0.0
    review_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ProductListResponse(BaseModel):
    products: List[ProductResponse]
    total: int
    page: int
    pages: int
