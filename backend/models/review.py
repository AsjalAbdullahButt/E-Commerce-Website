from pydantic import BaseModel, Field, field_validator
from utils.helpers import sanitize_input

class ReviewCreate(BaseModel):
    product_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: str

    @field_validator('comment')
    @classmethod
    def comment_valid(cls, v):
        v = sanitize_input(v, max_length=1000)
        if not v:
            raise ValueError('Comment cannot be empty')
        return v
