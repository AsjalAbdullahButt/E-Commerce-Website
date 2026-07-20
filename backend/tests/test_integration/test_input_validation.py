"""
Phase 2 polish pass — input validation/sanitization on free-text fields beyond what bare
Pydantic `str` typing enforces (NOTES_schema_audit.md, "Polish-pass Phase 2" section).
Covers: review comments, shipping addresses, order status notes, admin ban/adjust-stock
reasons/notes, and product name/description/category.

utils/helpers.py::sanitize_input's MongoDB-operator blacklist (Phase 3 hardening, 2026-07-20)
was removed: this is a MySQL app where SQLAlchemy's parameter binding already prevents SQL
injection regardless of string contents, so rejecting "$where"/"$ne"/etc. provided zero real
protection while blocking legitimate text that happened to contain one of those substrings.
The tests that used to assert those strings were rejected now assert the opposite -- and cover
the replacement checks (null byte rejection, Unicode NFKC normalization) instead.
"""
import asyncio

import pytest

from services.admin_auth import AdminAuthService
from utils.helpers import sanitize_input


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

def test_review_comment_accepts_dollar_sign_text(client):
    # "$where"-shaped substrings used to be rejected as a MongoDB-operator blacklist -- a
    # leftover from this app's pre-migration Mongo backend with zero relevance to a MySQL app
    # (SQLAlchemy's parameter binding is what actually prevents injection). Legitimate text like
    # a price mention must not be rejected just because it contains "$where"/"$gt"/etc.
    admin_token = _admin_token(client)
    customer_token = _register_customer(client)
    product_id = _create_product(client, admin_token)
    _place_and_deliver_order(client, admin_token, customer_token, product_id)

    resp = client.post(
        "/reviews",
        json={"product_id": product_id, "rating": 5, "comment": "Worth every $, no $where trick needed"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 200, resp.text


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


def test_order_accepts_dollar_sign_in_shipping_address(client):
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
                "full_name": "$ne Trading Co", "phone": "03001234567",
                "address": "1 Test Rd", "city": "Karachi", "postal_code": "75000",
            },
            "payment_method": "cod",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 200, resp.text


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


def test_add_order_note_accepts_dollar_sign_text(client):
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
        params={"note": "Customer asked about a $where clause in their custom integration"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text


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


# ── sanitize_input itself: the Phase 3 replacement checks ───────────────────────

def test_sanitize_input_rejects_null_byte():
    with pytest.raises(ValueError):
        sanitize_input("hello\x00world")


def test_sanitize_input_normalizes_unicode_nfkc():
    # U+FF21/22/23 (fullwidth "A"/"B"/"C") NFKC-normalize to plain ASCII "A"/"B"/"C" -- two
    # different code points that render identically, which would otherwise let visually
    # indistinguishable strings evade exact-match/duplicate-detection logic downstream.
    assert sanitize_input("ＡＢＣ") == "ABC"


def test_sanitize_input_strips_control_characters_but_keeps_newlines_and_tabs():
    assert sanitize_input("line one\nline\ttwo\x07") == "line one\nline\ttwo"


def test_sanitize_input_no_longer_rejects_dollar_operator_shaped_text():
    assert sanitize_input("cost $gt 100 and $lte 500") == "cost $gt 100 and $lte 500"


def test_review_comment_rejects_null_byte(client):
    admin_token = _admin_token(client)
    customer_token = _register_customer(client, email="nullbytecustomer@test.com")
    product_id = _create_product(client, admin_token)
    _place_and_deliver_order(client, admin_token, customer_token, product_id)

    resp = client.post(
        "/reviews",
        json={"product_id": product_id, "rating": 5, "comment": "great\x00product"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 422
