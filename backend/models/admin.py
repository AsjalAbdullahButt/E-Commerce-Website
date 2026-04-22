# MongoDB database models (document schemas)
from typing import Optional, List
from datetime import datetime
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
        "is_deleted": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
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
        "timestamp": datetime.utcnow(),
    }

def inventory_history_document(product_id: str) -> dict:
    """Create inventory history document"""
    return {
        "product_id": product_id,
        "logs": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

# ════════════════════════════════════════════════════════════════════════════
# ORDER DOCUMENT
# ════════════════════════════════════════════════════════════════════════════

def order_status_timeline_entry(status: str, note: Optional[str] = None) -> dict:
    """Create order status timeline entry"""
    return {
        "status": status,
        "timestamp": datetime.utcnow(),
        "note": note,
    }

def order_document(
    user_id: str,
    user_email: str,
    items: List[dict],
    shipping_address: dict,
    payment_method: str,
    total_price: float,
    discount_applied: float,
) -> dict:
    """Create order document"""
    return {
        "user_id": user_id,
        "user_email": user_email,
        "items": items,  # [{product_id, name, price, quantity, size, color, image}, ...]
        "shipping_address": shipping_address,
        "payment_method": payment_method,  # "cod", "jazzcash", "easypaisa"
        "payment_status": "pending",
        "total_price": total_price,
        "discount_applied": discount_applied,
        "final_price": total_price - discount_applied,
        "status": "pending",
        "timeline": [order_status_timeline_entry("pending")],
        "notes": [],
        "is_deleted": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

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
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

# ════════════════════════════════════════════════════════════════════════════
# DISCOUNT/COUPON DOCUMENT
# ════════════════════════════════════════════════════════════════════════════

def discount_document(
    code: str,
    description: str,
    discount_type: str,
    discount_value: float,
    max_usage: int,
    min_order_value: float,
    expiry_date: datetime,
    created_by: str,
) -> dict:
    """Create discount document"""
    return {
        "code": code.upper(),
        "description": description,
        "discount_type": discount_type,  # "percentage", "fixed"
        "discount_value": discount_value,
        "max_usage": max_usage,
        "current_usage": 0,
        "min_order_value": min_order_value,
        "is_active": True,
        "expiry_date": expiry_date,
        "created_by": created_by,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
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
        "timestamp": datetime.utcnow(),
        "ip_address": ip_address,
    }
