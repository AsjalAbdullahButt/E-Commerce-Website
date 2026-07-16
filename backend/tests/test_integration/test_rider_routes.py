"""
Fills gaps in rider.py route coverage: GET /rider/profile, GET /rider/earnings, and
GET /rider/orders/history had zero test coverage before this file (test_rider_admin.py covers
admin-side rider management and the assign/status/complete delivery flow, but not the rider's own
profile/earnings/history views).
"""
import asyncio

from services.admin_auth import AdminAuthService


def _admin_token(client, email="riderrouteadmin@test.com", password="AdminPass123"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role="admin"))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


def _create_and_login_rider(client, admin_token, email="routerider@test.com", name="Route Rider"):
    create_resp = client.post(
        "/admin/riders",
        json={"name": name, "email": email, "password": "RiderPass123", "phone": "03008888888"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_resp.status_code == 200, create_resp.text

    login_resp = client.post("/auth/login", json={"email": email, "password": "RiderPass123"})
    assert login_resp.status_code == 200, login_resp.text
    body = login_resp.json()
    assert body["user"]["role"] == "rider"
    return body["access_token"]


def test_rider_can_view_own_profile(client):
    admin_token = _admin_token(client)
    rider_token = _create_and_login_rider(client, admin_token)

    resp = client.get("/rider/profile", headers={"Authorization": f"Bearer {rider_token}"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["email"] == "routerider@test.com"
    assert "password" not in body["data"]


def test_customer_cannot_view_rider_profile(client):
    resp_register = client.post("/auth/register", json={
        "name": "Not A Rider", "email": "notarider@test.com", "password": "Shopper123", "phone": "03001234567",
    })
    customer_token = resp_register.json()["access_token"]

    resp = client.get("/rider/profile", headers={"Authorization": f"Bearer {customer_token}"})
    assert resp.status_code == 403


def test_rider_earnings_reachable_and_shaped(client):
    admin_token = _admin_token(client, email="riderrouteadmin2@test.com")
    rider_token = _create_and_login_rider(client, admin_token, email="routerider2@test.com", name="Route Rider 2")

    resp = client.get("/rider/earnings", headers={"Authorization": f"Bearer {rider_token}"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["total_deliveries"] == 0
    assert body["data"]["total_earnings"] == 0


def test_rider_orders_history_reachable(client):
    admin_token = _admin_token(client, email="riderrouteadmin3@test.com")
    rider_token = _create_and_login_rider(client, admin_token, email="routerider3@test.com", name="Route Rider 3")

    resp = client.get("/rider/orders/history", headers={"Authorization": f"Bearer {rider_token}"})
    assert resp.status_code == 200, resp.text
