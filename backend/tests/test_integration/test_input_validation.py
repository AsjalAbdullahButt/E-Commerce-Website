"""
Phase 2 polish pass — input validation/sanitization on free-text fields beyond what bare
Pydantic `str` typing enforces (NOTES_schema_audit.md, "Polish-pass Phase 2" section).
Covers: review comments, shipping addresses, order status notes, admin ban/adjust-stock
reasons/notes, and product name/description/category.
"""
import asyncio

from services.admin_auth import AdminAuthService


def _admin_token(client, email="validationadmin@test.com", password="AdminPass123", role="admin"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role=role))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


def _register_customer(client, email="validator@test.com", password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "Validator", "email": email, "password": password, "phone": "03001234567",
    })
    return resp.json()["access_token"]


def _create_product(client, admin_token):
    resp = client.post(
        "/admin/products",
        json={
            "name": "Validation Test Mug", "description": "mug", "category": "accessories",
            "price": 500, "discount_percentage": 0, "tags": [], "images": [],
            "variants": [{"size": "One Size", "color": "White", "sku": "validation-mug", "stock": 10}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return resp.json()["data"]["product_id"]


def _place_and_deliver_order(client, admin_token, customer_token, product_id):
    order_resp = client.post(
        "/orders",
        json={
            "items": [{
                "product_id": product_id, "name": "Validation Test Mug", "price": 500,
                "quantity": 1, "size": "One Size", "color": "White", "image": "",
            }],
            "shipping_address": {
                "full_name": "Validator", "phone": "03001234567",
                "address": "1 Test Rd", "city": "Karachi", "postal_code": "75000",
            },
            "payment_method": "cod",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    order_id = order_resp.json()["id"]
    for status in ["confirmed", "packed", "shipped", "delivered"]:
        r = client.put(f"/admin/orders/{order_id}/status", json={"status": status}, headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200, r.text
    return order_id


# ── Review comment ──────────────────────────────────────────────────────────────

def test_review_comment_rejects_nosql_operator(client):
    admin_token = _admin_token(client)
    customer_token = _register_customer(client)
    product_id = _create_product(client, admin_token)
    _place_and_deliver_order(client, admin_token, customer_token, product_id)

    resp = client.post(
        "/reviews",
        json={"product_id": product_id, "rating": 5, "comment": "nice $where trick"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 422


def test_review_comment_rejects_oversized_input(client):
    admin_token = _admin_token(client)
    customer_token = _register_customer(client)
    product_id = _create_product(client, admin_token)
    _place_and_deliver_order(client, admin_token, customer_token, product_id)

    resp = client.post(
        "/reviews",
        json={"product_id": product_id, "rating": 5, "comment": "x" * 1001},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 422


def test_review_comment_rejects_empty_after_strip(client):
    admin_token = _admin_token(client)
    customer_token = _register_customer(client)
    product_id = _create_product(client, admin_token)
    _place_and_deliver_order(client, admin_token, customer_token, product_id)

    resp = client.post(
        "/reviews",
        json={"product_id": product_id, "rating": 5, "comment": "   "},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 422


def test_review_comment_accepts_normal_text(client):
    admin_token = _admin_token(client)
    customer_token = _register_customer(client)
    product_id = _create_product(client, admin_token)
    _place_and_deliver_order(client, admin_token, customer_token, product_id)

    resp = client.post(
        "/reviews",
        json={"product_id": product_id, "rating": 5, "comment": "Great mug, fast delivery!"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 200, resp.text


# ── Shipping address (order placement) ──────────────────────────────────────────

def test_order_rejects_oversized_shipping_address(client):
    admin_token = _admin_token(client)
    customer_token = _register_customer(client)
    product_id = _create_product(client, admin_token)

    resp = client.post(
        "/orders",
        json={
            "items": [{
                "product_id": product_id, "name": "x", "price": 500,
                "quantity": 1, "size": "One Size", "color": "White", "image": "",
            }],
            "shipping_address": {
                "full_name": "Validator", "phone": "03001234567",
                "address": "a" * 301, "city": "Karachi", "postal_code": "75000",
            },
            "payment_method": "cod",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 422


def test_order_rejects_nosql_operator_in_shipping_address(client):
    admin_token = _admin_token(client)
    customer_token = _register_customer(client)
    product_id = _create_product(client, admin_token)

    resp = client.post(
        "/orders",
        json={
            "items": [{
                "product_id": product_id, "name": "x", "price": 500,
                "quantity": 1, "size": "One Size", "color": "White", "image": "",
            }],
            "shipping_address": {
                "full_name": "$ne", "phone": "03001234567",
                "address": "1 Test Rd", "city": "Karachi", "postal_code": "75000",
            },
            "payment_method": "cod",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 422


# ── Admin free-text: ban reason, order note, stock-adjust reason ───────────────

def test_ban_user_rejects_oversized_reason(client):
    # Only super_admin has "user:ban" in utils/permissions.py (see test_access_control.py).
    admin_token = _admin_token(client, email="banadmin1@test.com", role="super_admin")
    customer_token = _register_customer(client, email="banme@test.com")
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {customer_token}"}).json()

    resp = client.post(
        f"/admin/users/{me['id']}/ban",
        params={"reason": "x" * 301},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


def test_ban_user_accepts_normal_reason(client):
    admin_token = _admin_token(client, email="banadmin2@test.com", role="super_admin")
    customer_token = _register_customer(client, email="banme2@test.com")
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {customer_token}"}).json()

    resp = client.post(
        f"/admin/users/{me['id']}/ban",
        params={"reason": "Repeated policy violations"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text


def test_add_order_note_rejects_nosql_operator(client):
    admin_token = _admin_token(client)
    customer_token = _register_customer(client, email="notecustomer@test.com")
    product_id = _create_product(client, admin_token)
    order_resp = client.post(
        "/orders",
        json={
            "items": [{
                "product_id": product_id, "name": "x", "price": 500,
                "quantity": 1, "size": "One Size", "color": "White", "image": "",
            }],
            "shipping_address": {
                "full_name": "Validator", "phone": "03001234567",
                "address": "1 Test Rd", "city": "Karachi", "postal_code": "75000",
            },
            "payment_method": "cod",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    order_id = order_resp.json()["id"]

    resp = client.post(
        f"/admin/orders/{order_id}/note",
        params={"note": "$where malicious"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


def test_adjust_stock_rejects_oversized_reason(client):
    admin_token = _admin_token(client)
    product_id = _create_product(client, admin_token)

    resp = client.post(
        "/admin/inventory/adjust-stock",
        params={
            "product_id": product_id, "variant_sku": "validation-mug",
            "quantity_change": 5, "reason": "y" * 301,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


# ── Product name/description/category (admin product create) ──────────────────

def test_create_product_rejects_oversized_description(client):
    admin_token = _admin_token(client)
    resp = client.post(
        "/admin/products",
        json={
            "name": "Oversized Desc Product", "description": "d" * 5001, "category": "accessories",
            "price": 500, "discount_percentage": 0, "tags": [], "images": [],
            "variants": [{"size": "One Size", "color": "White", "sku": "oversize-1", "stock": 10}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


def test_create_product_rejects_empty_name(client):
    admin_token = _admin_token(client)
    resp = client.post(
        "/admin/products",
        json={
            "name": "   ", "description": "fine", "category": "accessories",
            "price": 500, "discount_percentage": 0, "tags": [], "images": [],
            "variants": [{"size": "One Size", "color": "White", "sku": "empty-name-1", "stock": 10}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422
