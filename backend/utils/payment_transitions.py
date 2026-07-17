from fastapi import HTTPException

# Single source of truth for legal payment-attempt status transitions (Payment.status, one row
# per attempt — see db/payment.py). Mirrors utils/order_transitions.py's shape/pattern.
#
# "initiated" can go straight to "paid"/"failed" (not just via "processing") because several
# gateways only ever send one final webhook and never an intermediate "processing" event.
VALID_PAYMENT_TRANSITIONS: dict[str, set[str]] = {
    "initiated":  {"processing", "paid", "failed"},
    "processing": {"paid", "failed"},
    "paid":       {"refunded"},
    "failed":     set(),   # terminal — a retry creates a new Payment row, not a transition
    "refunded":   set(),
}


def assert_valid_payment_transition(current_status: str, new_status: str) -> None:
    """Raise HTTP 400 if `current_status -> new_status` is not a legal payment transition."""
    allowed = VALID_PAYMENT_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition payment from '{current_status}' to '{new_status}'",
        )
