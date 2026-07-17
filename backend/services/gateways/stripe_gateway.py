from typing import Any

from config import settings
from db.order import Order
from services.gateways.base import PaymentGateway, WebhookResult


class StripeGateway(PaymentGateway):
    """Stripe PaymentIntents — the client confirms card details via Stripe.js/Elements using the
    returned client_secret, so raw card data never touches this server. Only the webhook (verified
    below) is trusted proof of payment; a client-side "it succeeded" call is never accepted."""

    name = "stripe"

    def is_configured(self) -> bool:
        return bool(settings.stripe_enabled and settings.stripe_secret_key and settings.stripe_webhook_secret)

    async def initiate(self, *, order: Order, payment_id: str) -> dict:
        import stripe

        stripe.api_key = settings.stripe_secret_key
        intent = stripe.PaymentIntent.create(
            amount=int(round(order.total * 100)),  # Stripe wants the smallest currency unit
            currency=settings.payment_currency.lower(),
            metadata={"order_id": order.id, "payment_id": payment_id},
            # Our own idempotency key, distinct from the client-facing Idempotency-Key header —
            # prevents a retried initiate() call from minting a second PaymentIntent even if our
            # own DB-level dedup (services/payment.py) somehow races.
            idempotency_key=f"pi-{payment_id}",
        )
        return {"client_secret": intent["client_secret"], "publishable_key": settings.stripe_publishable_key}

    def verify_webhook(self, *, headers: dict, body: bytes, params: dict) -> WebhookResult:
        import stripe

        sig_header = headers.get("stripe-signature")
        try:
            event = stripe.Webhook.construct_event(body, sig_header, settings.stripe_webhook_secret)
        except (ValueError, stripe.error.SignatureVerificationError) as exc:
            raise ValueError(f"Invalid Stripe webhook signature: {exc}")

        intent = event["data"]["object"]
        success = event["type"] == "payment_intent.succeeded"
        payment_id = (intent.get("metadata") or {}).get("payment_id")
        return WebhookResult(
            event_id=event["id"],
            payment_id=payment_id,
            transaction_id=intent.get("id"),
            success=success,
            raw=event if isinstance(event, dict) else dict(event),
        )
