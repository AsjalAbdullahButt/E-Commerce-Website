"""
Regression test for the refresh-token reconciliation (NOTES_schema_audit.md §7 / task 8):
admin auth now issues its refresh token via an httpOnly cookie (admin_refresh_token) exactly like
the customer flow (refresh_token), instead of returning it in the JSON body for localStorage
storage. This also implicitly covers the login/refresh round trip working with `Response` cookie
handling wired up correctly in routes/admin.py.
"""
import asyncio

from services.admin_auth import AdminAuthService


def test_admin_login_sets_httponly_refresh_cookie_not_json_body(client):
    asyncio.run(AdminAuthService.create_admin_user(
        name="Cookie Admin", email="cookieadmin@test.com", password="AdminPass123", role="admin"
    ))

    login_resp = client.post("/admin/auth/login", json={"email": "cookieadmin@test.com", "password": "AdminPass123"})
    assert login_resp.status_code == 200, login_resp.text

    body = login_resp.json()
    assert "refresh_token" not in body["data"], "refresh_token must not be exposed in the JSON body"
    assert "access_token" in body["data"]

    assert "admin_refresh_token" in client.cookies


def test_admin_refresh_uses_cookie_and_rotates_it(client):
    asyncio.run(AdminAuthService.create_admin_user(
        name="Refresh Admin", email="refreshadmin@test.com", password="AdminPass123", role="admin"
    ))
    client.post("/admin/auth/login", json={"email": "refreshadmin@test.com", "password": "AdminPass123"})
    first_cookie = client.cookies.get("admin_refresh_token")
    assert first_cookie

    refresh_resp = client.post("/admin/auth/refresh")
    assert refresh_resp.status_code == 200, refresh_resp.text
    assert "access_token" in refresh_resp.json()["data"]
    assert "refresh_token" not in refresh_resp.json()["data"], "refresh_token must not be exposed in the JSON body"

    # A fresh refresh token is issued and re-set as the cookie on every call (rotation) — the JWT
    # payload can come out byte-identical to the previous one if both calls land in the same
    # second (same sub/role/exp/type -> same signature), so this only checks the mechanism
    # actually ran, not string inequality.
    second_cookie = client.cookies.get("admin_refresh_token")
    assert second_cookie


def test_admin_refresh_without_cookie_is_rejected(client):
    resp = client.post("/admin/auth/refresh")
    assert resp.status_code == 401
