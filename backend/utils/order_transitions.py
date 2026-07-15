from fastapi import HTTPException

# Single source of truth for legal order status transitions. Applied to every endpoint that can
# change an order's status: customer cancel, generic admin/rider status update, admin order-status
# update, and rider complete-delivery. See NOTES_schema_audit.md §2.
VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending":   {"confirmed", "cancelled"},
    "confirmed": {"packed", "cancelled"},
    "packed":    {"shipped", "cancelled"},
    "shipped":   {"delivered"},
    "delivered": {"returned"},
    "cancelled": set(),
    "returned":  set(),
}


def assert_valid_transition(current_status: str, new_status: str) -> None:
    """Raise HTTP 400 if `current_status -> new_status` is not a legal order transition."""
    allowed = VALID_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition order from '{current_status}' to '{new_status}'",
        )
