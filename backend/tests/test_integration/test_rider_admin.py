"""
Regression tests for the admin-facing rider management build-out (NOTES_schema_audit.md §4):
before this, there was no way to create a rider except a manual DB insert, and assign-rider
never validated the rider existed, was active, or that the order wasn't already
delivered/cancelled.
"""
import asyncio

from services.admin_auth import AdminAuthService


def _admin_token(client, email="riderboss@test.com", password="AdminPass123"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role="admin"))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _register_customer(client, email="buyer@test.com", password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "Buyer", "email": email, "password": password, "phone": "03001234567",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _place_order(client, customer_token, admin_token):
    product_resp = client.post(
        "/admin/products",
        json={
            "name": "Rider Test Cap", "description": "cap", "category": "accessories",
            "price": 500, "discount_percentage": 0, "tags": [], "images": [],
            "variants": [{"size": "One Size", "color": "Black", "sku": "cap-black", "stock": 20}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    product_id = product_resp.json()["data"]["product_id"]

    order_resp = client.post(
        "/orders",
        json={
            "items": [{
                "product_id": product_id, "name": "Rider Test Cap", "price": 500,
                "quantity": 1, "size": "One Size", "color": "Black", "image": "",
            }],
            "shipping_address": {
                "full_name": "Buyer", "phone": "03001234567",
                "address": "1 Test Rd", "city": "Karachi", "postal_code": "75000",
            },
            "payment_method": "cod",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert order_resp.status_code == 200, order_resp.text
    return order_resp.json()["id"]


def test_admin_creates_rider_and_it_is_listed(client):
    admin_token = _admin_token(client)
    create_resp = client.post(
        "/admin/riders",
        json={"name": "Ali Rider", "email": "ali.rider@test.com", "password": "RiderPass123", "phone": "03009999999"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_resp.status_code == 200, create_resp.text
    rider = create_resp.json()["data"]
    assert rider["is_active"] is True
    assert rider["status"] == "offline"
    assert "password" not in rider

    list_resp = client.get("/admin/riders", headers={"Authorization": f"Bearer {admin_token}"})
    assert list_resp.status_code == 200
    emails = [r["email"] for r in list_resp.json()["data"]]
    assert "ali.rider@test.com" in emails


def test_rider_can_log_in_and_go_available(client):
    admin_token = _admin_token(client)
    client.post(
        "/admin/riders",
        json={"name": "Sara Rider", "email": "sara.rider@test.com", "password": "RiderPass123", "phone": "03008888888"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    login_resp = client.post("/auth/login", json={"email": "sara.rider@test.com", "password": "RiderPass123"})
    assert login_resp.status_code == 200, login_resp.text
    assert login_resp.json()["user"]["role"] == "rider"
    rider_token = login_resp.json()["access_token"]

    status_resp = client.patch("/rider/status?status=available", headers={"Authorization": f"Bearer {rider_token}"})
    assert status_resp.status_code == 200

    profile_resp = client.patch(
        "/rider/profile", json={"phone": "03007777777"},
        headers={"Authorization": f"Bearer {rider_token}"},
    )
    assert profile_resp.status_code == 200, profile_resp.text


def test_assign_rider_validates_existence_availability_and_order_state(client):
    admin_token = _admin_token(client)
    customer_token = _register_customer(client)

    rider_resp = client.post(
        "/admin/riders",
        json={"name": "Bilal Rider", "email": "bilal.rider@test.com", "password": "RiderPass123", "phone": "03006666666"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    rider_id = rider_resp.json()["data"]["id"]

    login_resp = client.post("/auth/login", json={"email": "bilal.rider@test.com", "password": "RiderPass123"})
    rider_token = login_resp.json()["access_token"]
    client.patch("/rider/status?status=available", headers={"Authorization": f"Bearer {rider_token}"})

    order_id = _place_order(client, customer_token, admin_token)

    # Non-existent rider is rejected.
    bad_assign = client.patch(
        f"/admin/orders/{order_id}/assign-rider?rider_id=000000000000000000000000",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert bad_assign.status_code == 400

    # Valid, available rider is accepted.
    good_assign = client.patch(
        f"/admin/orders/{order_id}/assign-rider?rider_id={rider_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert good_assign.status_code == 200, good_assign.text

    # Deactivated rider can no longer be assigned.
    client.patch(f"/admin/riders/{rider_id}/deactivate", headers={"Authorization": f"Bearer {admin_token}"})
    order_id_2 = _place_order(client, customer_token, admin_token)
    deactivated_assign = client.patch(
        f"/admin/orders/{order_id_2}/assign-rider?rider_id={rider_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert deactivated_assign.status_code == 400

    # Reactivate, then walk the order to 'delivered' and confirm assignment is now rejected.
    client.patch(f"/admin/riders/{rider_id}/activate", headers={"Authorization": f"Bearer {admin_token}"})
    client.put(f"/admin/orders/{order_id_2}/status", json={"status": "confirmed"}, headers={"Authorization": f"Bearer {admin_token}"})
    client.put(f"/admin/orders/{order_id_2}/status", json={"status": "packed"}, headers={"Authorization": f"Bearer {admin_token}"})
    client.put(f"/admin/orders/{order_id_2}/status", json={"status": "shipped"}, headers={"Authorization": f"Bearer {admin_token}"})
    client.put(f"/admin/orders/{order_id_2}/status", json={"status": "delivered"}, headers={"Authorization": f"Bearer {admin_token}"})

    delivered_assign = client.patch(
        f"/admin/orders/{order_id_2}/assign-rider?rider_id={rider_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert delivered_assign.status_code == 400


def test_rider_active_order_count(client):
    admin_token = _admin_token(client)
    customer_token = _register_customer(client)

    rider_resp = client.post(
        "/admin/riders",
        json={"name": "Zara Rider", "email": "zara.rider@test.com", "password": "RiderPass123", "phone": "03005555555"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    rider_id = rider_resp.json()["data"]["id"]
    login_resp = client.post("/auth/login", json={"email": "zara.rider@test.com", "password": "RiderPass123"})
    rider_token = login_resp.json()["access_token"]
    client.patch("/rider/status?status=available", headers={"Authorization": f"Bearer {rider_token}"})

    order_id = _place_order(client, customer_token, admin_token)
    client.patch(f"/admin/orders/{order_id}/assign-rider?rider_id={rider_id}", headers={"Authorization": f"Bearer {admin_token}"})

    count_resp = client.get(f"/admin/riders/{rider_id}/active-orders", headers={"Authorization": f"Bearer {admin_token}"})
    assert count_resp.status_code == 200
    assert count_resp.json()["data"]["active_orders"] == 1
