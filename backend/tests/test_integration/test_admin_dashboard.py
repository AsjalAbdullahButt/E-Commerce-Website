"""
Fills the largest gap found in the backend route-coverage audit: every dashboard/analytics
endpoint, the /admin/discounts CRUD, and /admin/audit-logs had zero test coverage (confirmed via
grep across the whole tests/ tree — only /admin/stats, /admin/orders, /admin/riders, /admin/users
had any prior tests). These are read-heavy aggregation endpoints, so coverage here is mainly:
(a) each one is reachable and returns 200 for a permitted admin, (b) the response shape actually
has the `data` envelope every other admin endpoint uses, (c) the /admin/discounts write path
round-trips correctly, (d) permission enforcement matches utils/permissions.py — "manager" has
dashboard:read but not promo:create, so it can read but not create a discount.
"""
import asyncio
from datetime import datetime, timedelta

from services.admin_auth import AdminAuthService


def _admin_token(client, email="dashadmin@test.com", password="AdminPass123", role="admin"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role=role))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


def test_dashboard_summary_reachable(client):
    token = _admin_token(client)
    resp = client.get("/admin/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text


def test_analytics_endpoints_reachable(client):
    token = _admin_token(client, email="dashadmin2@test.com")
    headers = {"Authorization": f"Bearer {token}"}
    for path in ("/admin/analytics/revenue", "/admin/analytics/orders", "/admin/analytics/users"):
        resp = client.get(path, headers=headers)
        assert resp.status_code == 200, f"{path} -> {resp.text}"


def test_dashboard_stat_endpoints_reachable(client):
    token = _admin_token(client, email="dashadmin3@test.com")
    headers = {"Authorization": f"Bearer {token}"}
    for path in (
        "/admin/dashboard/stats",
        "/admin/dashboard/revenue-trend",
        "/admin/dashboard/top-products",
        "/admin/dashboard/low-stock",
        "/admin/dashboard/recent-orders",
    ):
        resp = client.get(path, headers=headers)
        assert resp.status_code == 200, f"{path} -> {resp.text}"
        body = resp.json()
        assert body["success"] is True
        assert "data" in body


def test_dashboard_endpoints_require_admin_auth(client):
    resp = client.get("/admin/dashboard/stats")
    assert resp.status_code == 401


def test_audit_logs_reachable_and_shaped(client):
    token = _admin_token(client, email="dashadmin4@test.com")
    resp = client.get("/admin/audit-logs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert "total" in body


def test_admin_create_get_update_list_discount(client):
    token = _admin_token(client, email="dashadmin5@test.com")
    headers = {"Authorization": f"Bearer {token}"}
    expiry = (datetime.utcnow() + timedelta(days=30)).isoformat()

    create_resp = client.post(
        "/admin/discounts",
        json={
            "code": "DASH20", "description": "Dashboard test discount",
            "discount_type": "percentage", "discount_value": 20,
            "max_usage": 50, "min_order_value": 0, "expiry_date": expiry,
        },
        headers=headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    discount_id = create_resp.json()["data"]["discount_id"]

    get_resp = client.get(f"/admin/discounts/{discount_id}", headers=headers)
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["data"]["code"] == "DASH20"

    update_resp = client.put(
        f"/admin/discounts/{discount_id}",
        json={"description": "Updated description", "is_active": False},
        headers=headers,
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["data"]["is_active"] is False

    list_resp = client.get("/admin/discounts", headers=headers)
    assert list_resp.status_code == 200
    codes = [d["code"] for d in list_resp.json()["data"]]
    assert "DASH20" in codes


def test_manager_can_read_but_not_create_discount(client):
    """manager has promo:read but not promo:create (utils/permissions.py) — the admin UI's
    discount page should be usable read-only by a manager, matching the permission matrix."""
    token = _admin_token(client, email="dashmanager@test.com", role="manager")
    headers = {"Authorization": f"Bearer {token}"}

    list_resp = client.get("/admin/discounts", headers=headers)
    assert list_resp.status_code == 200

    create_resp = client.post(
        "/admin/discounts",
        json={
            "code": "MGRBLOCK", "description": "should be blocked",
            "discount_type": "fixed", "discount_value": 5,
            "max_usage": 10, "expiry_date": (datetime.utcnow() + timedelta(days=10)).isoformat(),
        },
        headers=headers,
    )
    assert create_resp.status_code == 403
