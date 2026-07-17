"""
Fills gaps in routes/orders.py coverage: GET /orders (bare admin list), PATCH /orders/{id}/status
(the customer-router's own status-transition path — distinct from /admin/orders/{id}/status, per
NOTES_schema_audit.md's note that four separate endpoints each apply transition validation and
needed a shared table), and POST /orders/{id}/cancel had no dedicated tests before this file.
"""
import asyncio

from services.admin_auth import AdminAuthService


def _admin_token(client, email="ordersrouteadmin@test.com", password="AdminPass123"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role="admin"))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


def _register_customer(client, email="ordersroutecustomer@test.com", password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "Orders Route Customer", "email": email, "password": password, "phone": "03001234567",
    })
    return resp.json()["access_token"]


def _create_product(client, admin_token, sku="orders-route-item"):
    resp = client.post(
        "/admin/products",
        json={
            "name": "Orders Route Item", "description": "test", "category": "accessories",
            "price": 400, "discount_percentage": 0, "tags": [], "images": [],
            "variants": [{"size": "One Size", "color": "Grey", "sku": sku, "stock": 15}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return resp.json()["data"]["product_id"]


def _place_order(client, customer_token, product_id):
    resp = client.post(
        "/orders",
        json={
            "items": [{
                "product_id": product_id, "name": "x", "price": 400,
                "quantity": 1, "size": "One Size", "color": "Grey", "image": "",
            }],
            "shipping_address": {
                "full_name": "Orders Route Customer", "phone": "03001234567",
                "address": "1 Test Rd", "city": "Karachi", "postal_code": "75000",
            },
            "payment_method": "cod",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def test_bare_orders_list_requires_admin(client):
    customer_token = _register_customer(client)
    resp = client.get("/orders", headers={"Authorization": f"Bearer {customer_token}"})
    assert resp.status_code == 403


def test_admin_can_list_all_orders(client):
    admin_token = _admin_token(client)
    customer_token = _register_customer(client, email="ordersroutecustomer2@test.com")
    product_id = _create_product(client, admin_token, sku="orders-route-item-2")
    order_id = _place_order(client, customer_token, product_id)

    resp = client.get("/orders", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200, resp.text
    ids = [o["id"] for o in resp.json()["data"]]
    assert order_id in ids


def test_admin_can_update_order_status_via_customer_router(client):
    admin_token = _admin_token(client, email="ordersrouteadmin2@test.com")
    customer_token = _register_customer(client, email="ordersroutecustomer3@test.com")
    product_id = _create_product(client, admin_token, sku="orders-route-item-3")
    order_id = _place_order(client, customer_token, product_id)

    resp = client.patch(
        f"/orders/{order_id}/status",
        json={"status": "confirmed", "note": "Confirmed via customer router"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text

    order_resp = client.get(f"/orders/{order_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert order_resp.json()["status"] == "confirmed"


def test_invalid_status_transition_rejected(client):
    admin_token = _admin_token(client, email="ordersrouteadmin3@test.com")
    customer_token = _register_customer(client, email="ordersroutecustomer4@test.com")
    product_id = _create_product(client, admin_token, sku="orders-route-item-4")
    order_id = _place_order(client, customer_token, product_id)

    # pending -> delivered directly skips the required intermediate states.
    resp = client.patch(
        f"/orders/{order_id}/status",
        json={"status": "delivered"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400


def test_customer_cannot_update_order_status(client):
    admin_token = _admin_token(client, email="ordersrouteadmin4@test.com")
    customer_token = _register_customer(client, email="ordersroutecustomer5@test.com")
    product_id = _create_product(client, admin_token, sku="orders-route-item-5")
    order_id = _place_order(client, customer_token, product_id)

    resp = client.patch(
        f"/orders/{order_id}/status",
        json={"status": "confirmed"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 403


def test_customer_can_cancel_own_pending_order(client):
    admin_token = _admin_token(client, email="ordersrouteadmin5@test.com")
    customer_token = _register_customer(client, email="ordersroutecustomer6@test.com")
    product_id = _create_product(client, admin_token, sku="orders-route-item-6")
    order_id = _place_order(client, customer_token, product_id)

    resp = client.post(f"/orders/{order_id}/cancel", headers={"Authorization": f"Bearer {customer_token}"})
    assert resp.status_code == 200, resp.text

    order_resp = client.get(f"/orders/{order_id}", headers={"Authorization": f"Bearer {customer_token}"})
    assert order_resp.json()["status"] == "cancelled"


def test_customer_cannot_cancel_another_users_order(client):
    admin_token = _admin_token(client, email="ordersrouteadmin6@test.com")
    owner_token = _register_customer(client, email="ordersrouteowner@test.com")
    other_token = _register_customer(client, email="ordersrouteintruder@test.com")
    product_id = _create_product(client, admin_token, sku="orders-route-item-7")
    order_id = _place_order(client, owner_token, product_id)

    resp = client.post(f"/orders/{order_id}/cancel", headers={"Authorization": f"Bearer {other_token}"})
    assert resp.status_code == 403


def test_cors_preflight_allows_idempotency_key_header(client):
    """Regression test: checkout.js sends Idempotency-Key on every POST /orders (cross-origin,
    frontend:5500 -> backend:8000). If it isn't in CORSMiddleware's allow_headers (main.py), the
    browser's preflight silently rejects the real request before checkout ever runs."""
    resp = client.options(
        "/orders",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "idempotency-key",
        },
    )
    assert resp.status_code == 200, resp.text
    allowed = resp.headers.get("access-control-allow-headers", "")
    assert "idempotency-key" in allowed.lower()


def test_cannot_cancel_a_shipped_order(client):
    """VALID_TRANSITIONS (utils/order_transitions.py) allows cancelling from pending/confirmed/
    packed, but not once an order has shipped — matches the real-world constraint that a package
    already in transit can't just be cancelled server-side."""
    admin_token = _admin_token(client, email="ordersrouteadmin7@test.com")
    customer_token = _register_customer(client, email="ordersroutecustomer7@test.com")
    product_id = _create_product(client, admin_token, sku="orders-route-item-8")
    order_id = _place_order(client, customer_token, product_id)

    for status in ("confirmed", "packed", "shipped"):
        r = client.patch(
            f"/orders/{order_id}/status",
            json={"status": status},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text

    resp = client.post(f"/orders/{order_id}/cancel", headers={"Authorization": f"Bearer {customer_token}"})
    assert resp.status_code == 400
