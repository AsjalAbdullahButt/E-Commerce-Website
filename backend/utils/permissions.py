ROLE_PERMISSIONS: dict[str, list[str]] = {
    "super_admin": [
        "product:create", "product:read", "product:update", "product:delete",
        "order:read", "order:update", "order:delete",
        "user:read", "user:update", "user:delete", "user:ban",
        "admin:read", "admin:create", "admin:update", "admin:delete",
        "audit:read", "inventory:read", "inventory:update",
        "promo:create", "promo:read", "promo:update", "promo:delete",
        "rider:create", "rider:read", "rider:update", "rider:delete",
        "dashboard:read", "settings:update",
    ],
    "admin": [
        "product:create", "product:read", "product:update",
        "order:read", "order:update",
        "user:read", "user:update",
        "audit:read", "inventory:read", "inventory:update",
        "promo:create", "promo:read", "promo:update",
        "rider:create", "rider:read", "rider:update",
        "dashboard:read",
    ],
    "manager": [
        "product:read", "product:update",
        "order:read", "order:update",
        "user:read", "inventory:read",
        "rider:read",
        "dashboard:read", "promo:read",
    ],
    "support": [
        "order:read", "user:read", "rider:read",
        "dashboard:read",
    ],
}


def has_permission(role: str, permission: str) -> bool:
    """Check if a role has a specific permission."""
    return permission in ROLE_PERMISSIONS.get(role, [])
