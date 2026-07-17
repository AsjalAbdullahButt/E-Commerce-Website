from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator

_KNOWN_GATEWAYS = {"stripe", "jazzcash", "easypaisa"}


class PaymentInitiateRequest(BaseModel):
    gateway: str
    idempotency_key: Optional[str] = None

    @field_validator("gateway")
    @classmethod
    def gateway_known(cls, v: str) -> str:
        v = (v or "").lower()
        if v not in _KNOWN_GATEWAYS:
            raise ValueError(f"gateway must be one of {sorted(_KNOWN_GATEWAYS)}")
        return v


class PaymentInitiateResponse(BaseModel):
    payment_id: str
    gateway: str
    status: Optional[str] = None
    redirect_url: Optional[str] = None
    form_fields: Optional[dict[str, Any]] = None
    client_secret: Optional[str] = None
    message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PaymentStatusResponse(BaseModel):
    order_id: str
    payment_status: str
    gateway: Optional[str] = None
    gateway_transaction_id: Optional[str] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
