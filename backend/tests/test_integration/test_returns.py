"""Tests for the returns/refund flow: POST /orders/{id}/return-request (customer/guest submit)
and GET/PATCH /admin/returns (admin queue + approve/reject) — see services/return_request.py.
"""
import asyncio

from services.admin_auth import AdminAuthService


def _admin_token(client, email="returnsadmin@test.com", password="AdminPass123"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role="admin"))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


def _register_customer(client, email="returnscustomer@test.com", password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "Returns Customer", "email": email, "password": password, "phone": "03001234567",
    })
    return resp.json()["access_token"]


def _create_product(client, admin_token, sku="returns-item", stock=15):
    resp = client.post(
        "/admin/products",
        json={
            "name": "Returns Item", "description": "test", "category": "accessories",
            "price": 900, "discount_percentage": 0, "tags": [], "images": [],
            "variants": [{"size": "One Size", "color": "Black", "sku": sku, "stock": stock}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return resp.json()["data"]["product_id"]


def _place_order(client, customer_token, product_id):
    resp = client.post(
        "/orders",
        json={
            "items": [{
                "product_id": product_id, "name": "x", "price": 900,
                "quantity": 1, "size": "One Size", "color": "Black", "image": "",
            }],
            "shipping_address": {
                "full_name": "Returns Customer", "phone": "03001234567",
                "address": "1 Returns Rd", "city": "Karachi", "postal_code": "75000",
            },
            "payment_method": "cod",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _advance_to_delivered(client, admin_token, order_id):
    for status in ("confirmed", "packed", "shipped", "delivered"):
        r = client.patch(
            f"/orders/{order_id}/status", json={"status": status},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text


def test_return_request_requires_delivered_order(client):
    admin_token = _admin_token(client)
    customer_token = _register_customer(client)
    product_id = _create_product(client, admin_token, sku="returns-item-1")
    order = _place_order(client, customer_token, product_id)  # still "pending"

    resp = client.post(
        f"/orders/{order['id']}/return-request", json={"reason": "Changed my mind"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 400


def test_customer_can_submit_return_request_on_delivered_order(client):
    admin_token = _admin_token(client, email="returnsadmin2@test.com")
    customer_token = _register_customer(client, email="returnscustomer2@test.com")
    product_id = _create_product(client, admin_token, sku="returns-item-2")
    order = _place_order(client, customer_token, product_id)
    _advance_to_delivered(client, admin_token, order["id"])

    resp = client.post(
        f"/orders/{order['id']}/return-request", json={"reason": "Item arrived damaged"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "pending"

    order_resp = client.get(f"/orders/{order['id']}", headers={"Authorization": f"Bearer {customer_token}"})
    assert order_resp.json()["return_request"]["status"] == "pending"


def test_cannot_submit_duplicate_pending_return_request(client):
    admin_token = _admin_token(client, email="returnsadmin3@test.com")
    customer_token = _register_customer(client, email="returnscustomer3@test.com")
    product_id = _create_product(client, admin_token, sku="returns-item-3")
    order = _place_order(client, customer_token, product_id)
    _advance_to_delivered(client, admin_token, order["id"])

    client.post(
        f"/orders/{order['id']}/return-request", json={"reason": "Item arrived damaged"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    resp = client.post(
        f"/orders/{order['id']}/return-request", json={"reason": "Second attempt"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 400


def test_non_owner_cannot_submit_return_request(client):
    admin_token = _admin_token(client, email="returnsadmin4@test.com")
    owner_token = _register_customer(client, email="returnsowner@test.com")
    other_token = _register_customer(client, email="returnsintruder@test.com")
    product_id = _create_product(client, admin_token, sku="returns-item-4")
    order = _place_order(client, owner_token, product_id)
    _advance_to_delivered(client, admin_token, order["id"])

    resp = client.post(
        f"/orders/{order['id']}/return-request", json={"reason": "Not mine"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


def test_admin_can_list_return_requests(client):
    admin_token = _admin_token(client, email="returnsadmin5@test.com")
    customer_token = _register_customer(client, email="returnscustomer5@test.com")
    product_id = _create_product(client, admin_token, sku="returns-item-5")
    order = _place_order(client, customer_token, product_id)
    _advance_to_delivered(client, admin_token, order["id"])
    client.post(
        f"/orders/{order['id']}/return-request", json={"reason": "Wrong size"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )

    resp = client.get("/admin/returns", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200, resp.text
    order_ids = [r["order_id"] for r in resp.json()["data"]]
    assert order["id"] in order_ids


def test_admin_approve_transitions_order_and_restores_stock(client):
    admin_token = _admin_token(client, email="returnsadmin6@test.com")
    customer_token = _register_customer(client, email="returnscustomer6@test.com")
    product_id = _create_product(client, admin_token, sku="returns-item-6", stock=5)
    order = _place_order(client, customer_token, product_id)  # decrements stock 5 -> 4
    _advance_to_delivered(client, admin_token, order["id"])
    return_resp = client.post(
        f"/orders/{order['id']}/return-request", json={"reason": "Doesn't fit"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    return_id = return_resp.json()["id"]

    resolve_resp = client.patch(
        f"/admin/returns/{return_id}", json={"action": "approve", "admin_note": "Approved, refund issued"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resolve_resp.status_code == 200, resolve_resp.text
    assert resolve_resp.json()["status"] == "approved"
    assert resolve_resp.json()["refund_amount"] == order["total"]

    order_resp = client.get(f"/orders/{order['id']}", headers={"Authorization": f"Bearer {admin_token}"})
    assert order_resp.json()["status"] == "returned"

    product_resp = client.get(f"/products/{product_id}")
    variant = product_resp.json()["variants"][0]
    assert variant["stock"] == 5  # restored


def test_admin_reject_leaves_order_delivered(client):
    admin_token = _admin_token(client, email="returnsadmin7@test.com")
    customer_token = _register_customer(client, email="returnscustomer7@test.com")
    product_id = _create_product(client, admin_token, sku="returns-item-7")
    order = _place_order(client, customer_token, product_id)
    _advance_to_delivered(client, admin_token, order["id"])
    return_resp = client.post(
        f"/orders/{order['id']}/return-request", json={"reason": "Just because"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    return_id = return_resp.json()["id"]

    resolve_resp = client.patch(
        f"/admin/returns/{return_id}", json={"action": "reject", "admin_note": "Outside policy"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resolve_resp.status_code == 200, resolve_resp.text
    assert resolve_resp.json()["status"] == "rejected"
    assert resolve_resp.json()["refund_amount"] is None

    order_resp = client.get(f"/orders/{order['id']}", headers={"Authorization": f"Bearer {admin_token}"})
    assert order_resp.json()["status"] == "delivered"  # unchanged


def test_admin_cannot_resolve_already_resolved_request(client):
    admin_token = _admin_token(client, email="returnsadmin8@test.com")
    customer_token = _register_customer(client, email="returnscustomer8@test.com")
    product_id = _create_product(client, admin_token, sku="returns-item-8")
    order = _place_order(client, customer_token, product_id)
    _advance_to_delivered(client, admin_token, order["id"])
    return_resp = client.post(
        f"/orders/{order['id']}/return-request", json={"reason": "Testing"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    return_id = return_resp.json()["id"]

    client.patch(
        f"/admin/returns/{return_id}", json={"action": "approve"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    second_resp = client.patch(
        f"/admin/returns/{return_id}", json={"action": "reject"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert second_resp.status_code == 400


def test_guest_can_submit_return_request_with_matching_email(client):
    admin_token = _admin_token(client, email="returnsadmin9@test.com")
    product_id = _create_product(client, admin_token, sku="returns-item-9")
    order = client.post("/orders", json={
        "items": [{
            "product_id": product_id, "name": "x", "price": 900,
            "quantity": 1, "size": "One Size", "color": "Black", "image": "",
        }],
        "shipping_address": {
            "full_name": "Guest Returner", "phone": "03001234567",
            "address": "1 Guest Rd", "city": "Karachi", "postal_code": "75000",
        },
        "payment_method": "cod",
        "guest_email": "returnsguest@test.com",
    }).json()
    _advance_to_delivered(client, admin_token, order["id"])

    resp = client.post(
        f"/orders/{order['id']}/return-request",
        params={"email": "returnsguest@test.com"},
        json={"reason": "Guest return"},
    )
    assert resp.status_code == 200, resp.text
