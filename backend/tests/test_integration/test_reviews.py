"""
Confirms routes/reviews.py::add_review's existing purchase-verification check still works
against the canonical order shape (status/items.product_id) — NOTES_schema_audit.md §7 flagged
this as already-correct during the STEP 0 audit; this test guards that against regression as the
order schema changes elsewhere in this pass.
"""
import asyncio

from services.admin_auth import AdminAuthService


def _admin_token(client, email="reviewadmin@test.com", password="AdminPass123"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role="admin"))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


def _register_customer(client, email="reviewer@test.com", password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "Reviewer", "email": email, "password": password, "phone": "03001234567",
    })
    return resp.json()["access_token"]


def _create_product(client, admin_token):
    resp = client.post(
        "/admin/products",
        json={
            "name": "Review Test Mug", "description": "mug", "category": "accessories",
            "price": 500, "discount_percentage": 0, "tags": [], "images": [],
            "variants": [{"size": "One Size", "color": "White", "sku": "review-mug", "stock": 10}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return resp.json()["data"]["product_id"]


def test_cannot_review_without_a_delivered_order(client):
    admin_token = _admin_token(client)
    customer_token = _register_customer(client)
    product_id = _create_product(client, admin_token)

    resp = client.post(
        "/reviews",
        json={"product_id": product_id, "rating": 5, "comment": "Great!"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 403


def test_can_review_after_delivered_order(client):
    admin_token = _admin_token(client)
    customer_token = _register_customer(client)
    product_id = _create_product(client, admin_token)

    order_resp = client.post(
        "/orders",
        json={
            "items": [{
                "product_id": product_id, "name": "Review Test Mug", "price": 500,
                "quantity": 1, "size": "One Size", "color": "White", "image": "",
            }],
            "shipping_address": {
                "full_name": "Reviewer", "phone": "03001234567",
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

    review_resp = client.post(
        "/reviews",
        json={"product_id": product_id, "rating": 4, "comment": "Pretty good"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert review_resp.status_code == 200, review_resp.text

    reviews = client.get(f"/reviews/{product_id}")
    assert len(reviews.json()) == 1
