"""Tests for the Phase 4 proof-of-delivery photo capture: POST /rider/orders/{id}/complete now
accepts an optional multipart `proof_photo`, stored via services/image_storage.py (category=
"delivery-proof") and persisted to Order.proof_of_delivery_url. See test_rider_admin.py for the
base assign/ship/complete flow this extends and test_image_upload.py for the underlying storage
service's own validation coverage (not re-tested here).
"""
import asyncio
import io

from PIL import Image

from services.admin_auth import AdminAuthService


def _admin_token(client, email="podadmin@test.com", password="AdminPass123"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role="admin"))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _register_customer(client, email="podbuyer@test.com", password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "POD Buyer", "email": email, "password": password, "phone": "03001234567",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _create_rider(client, admin_token, email="podrider@test.com", name="POD Rider"):
    create_resp = client.post(
        "/admin/riders",
        json={"name": name, "email": email, "password": "RiderPass123", "phone": "03007777777"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_resp.status_code == 200, create_resp.text
    rider_id = create_resp.json()["data"]["id"]

    login_resp = client.post("/auth/login", json={"email": email, "password": "RiderPass123"})
    assert login_resp.status_code == 200, login_resp.text
    rider_token = login_resp.json()["access_token"]
    client.patch("/rider/status?status=available", headers={"Authorization": f"Bearer {rider_token}"})
    return rider_id, rider_token


def _place_and_ship_order(client, customer_token, admin_token, rider_token, rider_id, sku="pod-item"):
    product_resp = client.post(
        "/admin/products",
        json={
            "name": "POD Test Item", "description": "test", "category": "accessories",
            "price": 500, "discount_percentage": 0, "tags": [], "images": [],
            "variants": [{"size": "One Size", "color": "Black", "sku": sku, "stock": 20}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    product_id = product_resp.json()["data"]["product_id"]

    order_resp = client.post(
        "/orders",
        json={
            "items": [{
                "product_id": product_id, "name": "POD Test Item", "price": 500,
                "quantity": 1, "size": "One Size", "color": "Black", "image": "",
            }],
            "shipping_address": {
                "full_name": "POD Buyer", "phone": "03001234567",
                "address": "1 Test Rd", "city": "Karachi", "postal_code": "75000",
            },
            "payment_method": "cod",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    order_id = order_resp.json()["id"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    client.put(f"/admin/orders/{order_id}/status", json={"status": "confirmed"}, headers=admin_headers)
    client.put(f"/admin/orders/{order_id}/status", json={"status": "packed"}, headers=admin_headers)
    client.patch(f"/admin/orders/{order_id}/assign-rider?rider_id={rider_id}", headers=admin_headers)
    ship_resp = client.patch(
        f"/rider/orders/{order_id}/status", json={"status": "shipped"},
        headers={"Authorization": f"Bearer {rider_token}"},
    )
    assert ship_resp.status_code == 200, ship_resp.text
    return order_id


def _fake_jpeg_bytes(color=(10, 200, 10)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (200, 200), color).save(buf, format="JPEG")
    return buf.getvalue()


def test_complete_delivery_with_photo_persists_and_serves_url(client):
    admin_token = _admin_token(client)
    customer_token = _register_customer(client)
    rider_id, rider_token = _create_rider(client, admin_token)
    order_id = _place_and_ship_order(client, customer_token, admin_token, rider_token, rider_id)

    resp = client.post(
        f"/rider/orders/{order_id}/complete",
        files={"proof_photo": ("delivery.jpg", _fake_jpeg_bytes(), "image/jpeg")},
        headers={"Authorization": f"Bearer {rider_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["proof_of_delivery_url"].startswith("http://testserver/uploads/delivery-proof/")

    # The order record itself carries the URL and is servable as a static file.
    order_view = client.get(f"/orders/{order_id}", headers={"Authorization": f"Bearer {customer_token}"})
    assert order_view.json()["status"] == "delivered"
    assert order_view.json()["proof_of_delivery_url"] == body["proof_of_delivery_url"]

    path = "/" + body["proof_of_delivery_url"].split("/", 3)[-1]
    fetch_resp = client.get(path)
    assert fetch_resp.status_code == 200
    assert fetch_resp.headers["content-type"].startswith("image/")


def test_order_response_includes_assigned_rider_name(client):
    """Phase 5 item 4: the customer-facing timeline (tracking.html) shows "Rider: <name>" on the
    shipped/delivered steps -- schemas/order.py::OrderResponse must actually carry rider_name
    (not just rider_id) or response_model silently drops it, same class of bug
    proof_of_delivery_url hit before it was added to that schema."""
    admin_token = _admin_token(client, email="podadmin3@test.com")
    customer_token = _register_customer(client, email="podbuyer3@test.com")
    rider_id, rider_token = _create_rider(client, admin_token, email="podrider3@test.com", name="Named Rider")
    order_id = _place_and_ship_order(client, customer_token, admin_token, rider_token, rider_id, sku="pod-item-3")

    order_view = client.get(f"/orders/{order_id}", headers={"Authorization": f"Bearer {customer_token}"})
    assert order_view.status_code == 200, order_view.text
    body = order_view.json()
    assert body["rider_id"] == rider_id
    assert body["rider_name"] == "Named Rider"


def test_complete_delivery_without_photo_still_works(client):
    """Backward-compat: the photo is optional at the API level (enforced client-side only)."""
    admin_token = _admin_token(client, email="podadmin2@test.com")
    customer_token = _register_customer(client, email="podbuyer2@test.com")
    rider_id, rider_token = _create_rider(client, admin_token, email="podrider2@test.com", name="POD Rider 2")
    order_id = _place_and_ship_order(client, customer_token, admin_token, rider_token, rider_id, sku="pod-item-2")

    resp = client.post(f"/rider/orders/{order_id}/complete", headers={"Authorization": f"Bearer {rider_token}"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["proof_of_delivery_url"] is None

    order_view = client.get(f"/orders/{order_id}", headers={"Authorization": f"Bearer {customer_token}"})
    assert order_view.json()["status"] == "delivered"
    assert order_view.json()["proof_of_delivery_url"] is None


def test_complete_delivery_rejects_invalid_image(client):
    admin_token = _admin_token(client, email="podadmin3@test.com")
    customer_token = _register_customer(client, email="podbuyer3@test.com")
    rider_id, rider_token = _create_rider(client, admin_token, email="podrider3@test.com", name="POD Rider 3")
    order_id = _place_and_ship_order(client, customer_token, admin_token, rider_token, rider_id, sku="pod-item-3")

    resp = client.post(
        f"/rider/orders/{order_id}/complete",
        files={"proof_photo": ("not-a-photo.txt", b"hello world", "text/plain")},
        headers={"Authorization": f"Bearer {rider_token}"},
    )
    assert resp.status_code == 400
    assert "Unsupported image type" in resp.json()["detail"]

    # And the order must NOT have been marked delivered by the failed attempt.
    order_view = client.get(f"/orders/{order_id}", headers={"Authorization": f"Bearer {customer_token}"})
    assert order_view.json()["status"] == "shipped"


def test_complete_delivery_rejects_unassigned_rider(client):
    admin_token = _admin_token(client, email="podadmin4@test.com")
    customer_token = _register_customer(client, email="podbuyer4@test.com")
    rider_id, rider_token = _create_rider(client, admin_token, email="podrider4@test.com", name="POD Rider 4")
    _, other_rider_token = _create_rider(client, admin_token, email="podrider4b@test.com", name="POD Rider 4b")
    order_id = _place_and_ship_order(client, customer_token, admin_token, rider_token, rider_id, sku="pod-item-4")

    resp = client.post(
        f"/rider/orders/{order_id}/complete",
        files={"proof_photo": ("delivery.jpg", _fake_jpeg_bytes(), "image/jpeg")},
        headers={"Authorization": f"Bearer {other_rider_token}"},
    )
    assert resp.status_code == 403
