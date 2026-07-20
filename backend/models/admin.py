# MongoDB database models (document schemas)
from typing import Optional, List
from datetime import datetime, timezone
from schemas.admin import AdminRole, OrderStatus, PaymentMethod, DiscountType, ProductVariant

# ════════════════════════════════════════════════════════════════════════════
# PRODUCT DOCUMENT
# ════════════════════════════════════════════════════════════════════════════

def product_document(
    name: str,
    description: str,
    category: str,
    price: float,
    discount_percentage: float,
    variants: List[dict],
    tags: List[str],
    images: List[str],
) -> dict:
    """Create product document for MongoDB"""
    total_stock = sum(v.get('stock', 0) for v in variants)
    
    return {
        "name": name,
        "description": description,
        "category": category,
        "price": price,
        "discount_percentage": discount_percentage,
        "discount_price": price * (1 - discount_percentage / 100),
        "variants": variants,  # [{size, color, sku, stock}, ...]
        "tags": tags,
        "images": images,
        "total_stock": total_stock,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "created_by": None,  # admin_id
    }

# ════════════════════════════════════════════════════════════════════════════
# INVENTORY HISTORY DOCUMENT
# ════════════════════════════════════════════════════════════════════════════

def inventory_log_entry(
    product_id: str,
    variant_sku: str,
    quantity_changed: int,
    reason: str,
    admin_id: Optional[str] = None,
) -> dict:
    """Create inventory log entry"""
    return {
        "product_id": product_id,
        "variant_sku": variant_sku,
        "quantity_changed": quantity_changed,
        "reason": reason,  # "order", "adjustment", "return", etc.
        "admin_id": admin_id,
        "timestamp": datetime.now(timezone.utc),
    }

def inventory_history_document(product_id: str) -> dict:
    """Create inventory history document"""
    return {
        "product_id": product_id,
        "logs": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

# NOTE: order documents are created exclusively by routes/orders.py::place_order (the real
# checkout path) — there is no admin.py-side order_document() builder. See NOTES_schema_audit.md §2.

# ════════════════════════════════════════════════════════════════════════════
# ADMIN USER DOCUMENT
# ════════════════════════════════════════════════════════════════════════════

def admin_user_document(
    name: str,
    email: str,
    password_hash: str,
    role: str,
) -> dict:
    """Create admin user document"""
    return {
        "name": name,
        "email": email,
        "password_hash": password_hash,
        "role": role,  # "super_admin", "admin", "manager", "support"
        "is_active": True,
        "is_locked": False,
        "failed_login_attempts": 0,
        "last_locked_at": None,
        "last_login": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

# ════════════════════════════════════════════════════════════════════════════
# AUDIT LOG DOCUMENT
# ════════════════════════════════════════════════════════════════════════════

def audit_log_document(
    admin_id: str,
    admin_name: str,
    action: str,
    entity_type: str,
    entity_id: str,
    changes: dict,
    ip_address: str,
) -> dict:
    """Create audit log document"""
    return {
        "admin_id": admin_id,
        "admin_name": admin_name,
        "action": action,  # "create", "update", "delete", "status_change", etc.
        "entity_type": entity_type,  # "product", "order", "user", "discount", etc.
        "entity_id": entity_id,
        "changes": changes,  # {"field": {"old": value, "new": value}, ...}
        "timestamp": datetime.now(timezone.utc),
        "ip_address": ip_address,
    }
