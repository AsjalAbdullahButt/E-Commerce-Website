"""Tests for guest checkout — POST /orders without an Authorization header (guest_email
required instead), and the guest order lookup path on GET /orders/{id}?email=... . See
middleware/auth_middleware.py::get_current_user_optional and routes/orders.py::place_order.
"""
import asyncio

from services.admin_auth import AdminAuthService


def _admin_token(client, email="guestadmin@test.com", password="AdminPass123"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role="admin"))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


def _register_customer(client, email="guestordercustomer@test.com", password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "Order Customer", "email": email, "password": password, "phone": "03001234567",
    })
    return resp.json()["access_token"]


def _create_product(client, admin_token, sku="guest-item"):
    resp = client.post(
        "/admin/products",
        json={
            "name": "Guest Item", "description": "test", "category": "accessories",
            "price": 800, "discount_percentage": 0, "tags": [], "images": [],
            "variants": [{"size": "One Size", "color": "Grey", "sku": sku, "stock": 15}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return resp.json()["data"]["product_id"]


def _guest_order_payload(product_id, guest_email="guest1@test.com", payment_method="cod"):
    return {
        "items": [{
            "product_id": product_id, "name": "x", "price": 800,
            "quantity": 1, "size": "One Size", "color": "Grey", "image": "",
        }],
        "shipping_address": {
            "full_name": "Guest Shopper", "phone": "03001234567",
            "address": "1 Guest Rd", "city": "Lahore", "postal_code": "54000",
        },
        "payment_method": payment_method,
        "guest_email": guest_email,
    }


def test_guest_checkout_requires_guest_email(client):
    admin_token = _admin_token(client)
    product_id = _create_product(client, admin_token)
    payload = _guest_order_payload(product_id)
    del payload["guest_email"]

    resp = client.post("/orders", json=payload)  # no Authorization header, no guest_email
    assert resp.status_code == 400
    assert "guest_email" in resp.json()["detail"]


def test_guest_checkout_creates_order_without_account(client):
    admin_token = _admin_token(client, email="guestadmin2@test.com")
    product_id = _create_product(client, admin_token, sku="guest-item-2")

    resp = client.post("/orders", json=_guest_order_payload(product_id, "guest2@test.com"))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["user_id"] is None
    assert data["guest_email"] == "guest2@test.com"
    assert data["status"] == "pending"


def test_guest_can_look_up_own_order_with_matching_email(client):
    admin_token = _admin_token(client, email="guestadmin3@test.com")
    product_id = _create_product(client, admin_token, sku="guest-item-3")
    order = client.post("/orders", json=_guest_order_payload(product_id, "guest3@test.com")).json()

    resp = client.get(f"/orders/{order['id']}", params={"email": "guest3@test.com"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == order["id"]


def test_guest_lookup_rejects_wrong_email(client):
    admin_token = _admin_token(client, email="guestadmin4@test.com")
    product_id = _create_product(client, admin_token, sku="guest-item-4")
    order = client.post("/orders", json=_guest_order_payload(product_id, "guest4@test.com")).json()

    resp = client.get(f"/orders/{order['id']}", params={"email": "wrong@test.com"})
    assert resp.status_code == 403


def test_guest_lookup_rejects_missing_email(client):
    admin_token = _admin_token(client, email="guestadmin5@test.com")
    product_id = _create_product(client, admin_token, sku="guest-item-5")
    order = client.post("/orders", json=_guest_order_payload(product_id, "guest5@test.com")).json()

    resp = client.get(f"/orders/{order['id']}")  # no email param, no auth
    assert resp.status_code == 403


def test_logged_in_customer_cannot_view_another_persons_guest_order(client):
    admin_token = _admin_token(client, email="guestadmin6@test.com")
    product_id = _create_product(client, admin_token, sku="guest-item-6")
    order = client.post("/orders", json=_guest_order_payload(product_id, "guest6@test.com")).json()

    customer_token = _register_customer(client, email="guestordercustomer2@test.com")
    resp = client.get(f"/orders/{order['id']}", headers={"Authorization": f"Bearer {customer_token}"})
    assert resp.status_code == 403


def test_guest_checkout_idempotency_key_returns_same_order(client):
    admin_token = _admin_token(client, email="guestadmin7@test.com")
    product_id = _create_product(client, admin_token, sku="guest-item-7")
    headers = {"Idempotency-Key": "guest-idem-key-1"}

    order1 = client.post("/orders", json=_guest_order_payload(product_id, "guest7@test.com"), headers=headers).json()
    order2 = client.post("/orders", json=_guest_order_payload(product_id, "guest7@test.com"), headers=headers).json()
    assert order1["id"] == order2["id"]


def test_guest_can_initiate_payment_for_own_order(client):
    """No account to check ownership against for a guest order — proves the endpoint doesn't
    401/403 an unauthenticated guest before even reaching the "gateway not configured" check."""
    admin_token = _admin_token(client, email="guestadmin9@test.com")
    product_id = _create_product(client, admin_token, sku="guest-item-9")
    order = client.post("/orders", json=_guest_order_payload(product_id, "guest9@test.com", "jazzcash")).json()

    resp = client.post(f"/payments/{order['id']}/initiate", json={"gateway": "jazzcash"})
    assert resp.status_code == 503  # unconfigured, not 401/403 — proves auth wasn't the blocker


def test_guest_can_poll_payment_status_for_own_order(client):
    admin_token = _admin_token(client, email="guestadmin10@test.com")
    product_id = _create_product(client, admin_token, sku="guest-item-10")
    order = client.post("/orders", json=_guest_order_payload(product_id, "guest10@test.com", "jazzcash")).json()

    resp = client.get(f"/payments/{order['id']}/status")
    assert resp.status_code == 200, resp.text
    assert resp.json()["payment_status"] == "unpaid"


def test_stranger_cannot_poll_payment_status_for_a_logged_in_customers_order(client):
    admin_token = _admin_token(client, email="guestadmin11@test.com")
    product_id = _create_product(client, admin_token, sku="guest-item-11")
    customer_token = _register_customer(client, email="guestordercustomer3@test.com")
    order = client.post(
        "/orders",
        json={**_guest_order_payload(product_id, "unused@test.com"), "guest_email": None},
        headers={"Authorization": f"Bearer {customer_token}"},
    ).json()

    resp = client.get(f"/payments/{order['id']}/status")  # unauthenticated
    assert resp.status_code == 403


def test_guest_can_cancel_own_pending_order(client):
    admin_token = _admin_token(client, email="guestadmin12@test.com")
    product_id = _create_product(client, admin_token, sku="guest-item-12")
    order = client.post("/orders", json=_guest_order_payload(product_id, "guest12@test.com")).json()

    resp = client.post(f"/orders/{order['id']}/cancel", params={"email": "guest12@test.com"})
    assert resp.status_code == 200, resp.text

    order_resp = client.get(f"/orders/{order['id']}", params={"email": "guest12@test.com"})
    assert order_resp.json()["status"] == "cancelled"


def test_guest_cannot_cancel_with_wrong_email(client):
    admin_token = _admin_token(client, email="guestadmin13@test.com")
    product_id = _create_product(client, admin_token, sku="guest-item-13")
    order = client.post("/orders", json=_guest_order_payload(product_id, "guest13@test.com")).json()

    resp = client.post(f"/orders/{order['id']}/cancel", params={"email": "wrong@test.com"})
    assert resp.status_code == 403


def test_admin_order_list_includes_guest_orders(client):
    admin_token = _admin_token(client, email="guestadmin8@test.com")
    product_id = _create_product(client, admin_token, sku="guest-item-8")
    order = client.post("/orders", json=_guest_order_payload(product_id, "guest8@test.com")).json()

    resp = client.get("/orders", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200, resp.text
    ids = [o["id"] for o in resp.json()["data"]]
    assert order["id"] in ids
