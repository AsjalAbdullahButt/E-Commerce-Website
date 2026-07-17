import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Any

from config import settings
from db.order import Order
from services.gateways.base import PaymentGateway, WebhookResult

_SANDBOX_URL = "https://sandbox.jazzcash.com.pk/CustomerPortal/transactionmanagement/merchantform/"
_LIVE_URL = "https://payments.jazzcash.com.pk/CustomerPortal/transactionmanagement/merchantform/"


class JazzCashGateway(PaymentGateway):
    """JazzCash Hosted Checkout Page (HCP) — redirect-based, no special merchant tier required.
    The customer is redirected to JazzCash's own page to approve the payment, then redirected
    back; the redirect is UX only, pp_SecureHash verification on the server-to-server callback
    (verify_webhook below) is the only thing ever treated as proof of payment.

    NOTE: field names/hash construction below follow JazzCash's published HCP guide (pp_*
    request fields, pp_SecureHash = HMAC-SHA256 over the sorted pp_ fields keyed by the
    Integrity Salt), but JazzCash has revised exact field sets across merchant account versions
    in the past. Confirm this against your merchant's own integration guide/Postman collection
    once real sandbox credentials are available, before going live — this is stubbed off
    (jazzcash_enabled=False) until then.
    """

    name = "jazzcash"

    def is_configured(self) -> bool:
        return bool(
            settings.jazzcash_enabled
            and settings.jazzcash_merchant_id
            and settings.jazzcash_password
            and settings.jazzcash_integrity_salt
        )

    def _secure_hash(self, fields: dict) -> str:
        # Sort pp_ fields alphabetically by key, join non-empty values with '&', prefix with the
        # Integrity Salt, HMAC-SHA256 keyed by the same salt, uppercase hex.
        ordered_values = "&".join(str(fields[k]) for k in sorted(fields) if fields.get(k) not in (None, ""))
        message = f"{settings.jazzcash_integrity_salt}&{ordered_values}"
        digest = hmac.new(
            settings.jazzcash_integrity_salt.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return digest.upper()

    async def initiate(self, *, order: Order, payment_id: str) -> dict:
        now = datetime.utcnow()
        # pp_TxnRefNo carries our own payment_id (prefixed "T" since JazzCash requires an
        # alphabetic lead character) so the callback can be matched straight back to this
        # attempt — see verify_webhook. Some JazzCash account versions cap this field at 20
        # chars; payment_id (24 hex chars) plus the prefix exceeds that on those versions —
        # confirm the real limit against your merchant guide before going live.
        fields = {
            "pp_Version": "1.1",
            "pp_TxnType": "MWALLET",
            "pp_Language": "EN",
            "pp_MerchantID": settings.jazzcash_merchant_id,
            "pp_SubMerchantID": "",
            "pp_Password": settings.jazzcash_password,
            "pp_TxnRefNo": f"T{payment_id}",
            "pp_Amount": str(int(round(order.total * 100))),  # paisas, integer, no decimal point
            "pp_TxnCurrency": settings.payment_currency,
            "pp_TxnDateTime": now.strftime("%Y%m%d%H%M%S"),
            "pp_BillReference": order.id,
            "pp_Description": f"Order {order.id}",
            "pp_TxnExpiryDateTime": (now + timedelta(hours=1)).strftime("%Y%m%d%H%M%S"),
            "pp_ReturnURL": settings.jazzcash_return_url or "",
        }
        fields["pp_SecureHash"] = self._secure_hash(fields)
        url = _SANDBOX_URL if settings.jazzcash_sandbox else _LIVE_URL
        return {"redirect_url": url, "form_fields": fields}

    def verify_webhook(self, *, headers: dict, body: bytes, params: dict) -> WebhookResult:
        received_hash = params.get("pp_SecureHash", "")
        check_fields = {k: v for k, v in params.items() if k.startswith("pp_") and k != "pp_SecureHash"}
        expected_hash = self._secure_hash(check_fields)
        if not received_hash or not hmac.compare_digest(received_hash.upper(), expected_hash):
            raise ValueError("pp_SecureHash mismatch")

        success = params.get("pp_ResponseCode") == "000"
        txn_ref = params.get("pp_TxnRefNo", "")
        payment_id = txn_ref[1:] if txn_ref.startswith("T") else None
        retrieval_ref = params.get("pp_RetreivalReferenceNo", "")
        return WebhookResult(
            event_id=f"jazzcash:{txn_ref}:{retrieval_ref}",
            payment_id=payment_id,
            transaction_id=retrieval_ref or txn_ref or None,
            success=success,
            raw=dict(params),
        )
