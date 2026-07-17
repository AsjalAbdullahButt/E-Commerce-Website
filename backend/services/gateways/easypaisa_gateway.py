import base64
import hashlib
import hmac
from typing import Any

from config import settings
from db.order import Order
from services.gateways.base import PaymentGateway, WebhookResult

_SANDBOX_URL = "https://easypaystg.easypaisa.com.pk/easypay/Index.jsf"
_LIVE_URL = "https://easypay.easypaisa.com.pk/easypay/Index.jsf"


class EasyPaisaGateway(PaymentGateway):
    """EasyPaisa hosted checkout — redirect-based, same integration tier as JazzCash HCP above.
    orderRefNum is documented as "merchant-generated order reference number" — used here to carry
    our own payment_id straight through so the postback can be matched back without guessing.

    NOTE: exact field names and hash encoding (this implementation uses HMAC-SHA256, base64-
    encoded) are gated behind EasyPaisa's merchant portal integration guide and have varied
    across guide revisions. Confirm this against your merchant's copy of the Easypaisa Merchant
    Integration Guide once real sandbox credentials are available, before going live — this is
    stubbed off (easypaisa_enabled=False) until then.
    """

    name = "easypaisa"

    def is_configured(self) -> bool:
        return bool(settings.easypaisa_enabled and settings.easypaisa_store_id and settings.easypaisa_hash_key)

    def _hashed_request(self, fields: dict) -> str:
        ordered = "&".join(f"{k}={fields[k]}" for k in sorted(fields) if fields.get(k) not in (None, ""))
        digest = hmac.new(
            settings.easypaisa_hash_key.encode("utf-8"),
            ordered.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(digest).decode("utf-8")

    async def initiate(self, *, order: Order, payment_id: str) -> dict:
        fields = {
            "storeId": settings.easypaisa_store_id,
            "amount": f"{order.total:.1f}",
            "postBackURL": settings.easypaisa_return_url or "",
            "orderRefNum": payment_id,
            "autoRedirect": "1",
            "paymentMethod": "InitialRequest",
        }
        fields["merchantHashedReq"] = self._hashed_request(fields)
        url = _SANDBOX_URL if settings.easypaisa_sandbox else _LIVE_URL
        return {"redirect_url": url, "form_fields": fields}

    def verify_webhook(self, *, headers: dict, body: bytes, params: dict) -> WebhookResult:
        received_hash = params.get("merchantHashedReq", "")
        check_fields = {k: v for k, v in params.items() if k != "merchantHashedReq"}
        expected_hash = self._hashed_request(check_fields)
        if not received_hash or not hmac.compare_digest(received_hash, expected_hash):
            raise ValueError("merchantHashedReq mismatch")

        success = params.get("status", "").upper() in ("PAID", "SUCCESS", "0000", "0")
        payment_id = params.get("orderRefNum") or None
        transaction_id = params.get("transactionId") or payment_id
        return WebhookResult(
            event_id=f"easypaisa:{payment_id}:{transaction_id}",
            payment_id=payment_id,
            transaction_id=transaction_id,
            success=success,
            raw=dict(params),
        )
