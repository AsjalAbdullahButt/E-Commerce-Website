from abc import ABC, abstractmethod
from typing import Any, Optional


class WebhookResult:
    """Normalized shape every gateway's callback/webhook verification produces, regardless of
    that gateway's own payload format — services/payment.py only ever deals with this, never a
    gateway-specific dict.

    payment_id is OUR OWN Payment.id, recovered from whatever reference field the gateway echoes
    back (Stripe: PaymentIntent metadata; JazzCash: pp_TxnRefNo; EasyPaisa: orderRefNum) — each
    gateway's initiate() embeds payment_id in that field specifically so the webhook can look the
    attempt up directly rather than guessing via order/transaction IDs.
    """

    def __init__(
        self,
        event_id: str,
        payment_id: Optional[str],
        transaction_id: Optional[str],
        success: bool,
        raw: dict,
    ):
        self.event_id = event_id
        self.payment_id = payment_id
        self.transaction_id = transaction_id
        self.success = success
        self.raw = raw


class PaymentGateway(ABC):
    """Common interface every gateway (Stripe / JazzCash / EasyPaisa) implements. A gateway is
    never called unless is_configured() is True — see services/payment.py."""

    name: str

    @abstractmethod
    def is_configured(self) -> bool:
        """False when the gateway's *_enabled flag is off or required credentials are missing —
        callers must treat this as 'this payment method isn't available', not an error."""
        ...

    @abstractmethod
    async def initiate(self, *, order: Any, payment_id: str) -> dict:
        """Start a payment attempt. Returns exactly what the client needs to complete payment —
        some subset of {redirect_url, form_fields, client_secret} — which is also stored verbatim
        as Payment.raw_response so a retried initiate call can re-serve the same values."""
        ...

    @abstractmethod
    def verify_webhook(self, *, headers: dict, body: bytes, params: dict) -> WebhookResult:
        """Verify a gateway callback/webhook's signature and normalize it. Must raise ValueError
        on a signature that doesn't check out — never trust an unverified payload as proof of
        payment."""
        ...
