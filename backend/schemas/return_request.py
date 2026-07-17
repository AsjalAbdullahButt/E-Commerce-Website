from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from utils.helpers import sanitize_input


class ReturnRequestCreate(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_valid(cls, v):
        v = sanitize_input(v, max_length=1000)
        if not v or len(v) < 5:
            raise ValueError("Please provide a reason of at least 5 characters")
        return v


class ReturnRequestAction(str, Enum):
    approve = "approve"
    reject = "reject"


class ReturnRequestResolve(BaseModel):
    action: ReturnRequestAction
    admin_note: Optional[str] = None
    refund_amount: Optional[float] = None  # only used when action == approve; defaults to order.total

    @field_validator("admin_note")
    @classmethod
    def note_valid(cls, v):
        if v is None:
            return v
        return sanitize_input(v, max_length=1000)


class ReturnRequestResponse(BaseModel):
    id: str
    order_id: str
    reason: str
    status: str
    refund_amount: Optional[float] = None
    admin_note: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ReturnRequestListResponse(BaseModel):
    data: list[ReturnRequestResponse]
    total: int
    page: int
    pages: int
