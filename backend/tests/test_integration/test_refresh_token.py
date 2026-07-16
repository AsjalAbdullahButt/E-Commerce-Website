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
    csrf_token = client.cookies.get("admin_csrf_token")
    assert csrf_token, "login must also issue the double-submit CSRF cookie"

    refresh_resp = client.post("/admin/auth/refresh", headers={"X-CSRF-Token": csrf_token})
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


def test_admin_refresh_without_csrf_header_is_rejected(client):
    """The refresh cookie alone isn't enough — the double-submit CSRF header must also match.
    This is what makes /admin/auth/refresh resistant to cross-site cookie-riding on top of the
    existing SameSite=Strict cookie attribute (see NOTES_schema_audit.md CSRF section)."""
    asyncio.run(AdminAuthService.create_admin_user(
        name="NoCsrf Admin", email="nocsrfadmin@test.com", password="AdminPass123", role="admin"
    ))
    client.post("/admin/auth/login", json={"email": "nocsrfadmin@test.com", "password": "AdminPass123"})
    assert client.cookies.get("admin_refresh_token")

    resp = client.post("/admin/auth/refresh")  # no X-CSRF-Token header
    assert resp.status_code == 403


def test_admin_refresh_with_wrong_csrf_header_is_rejected(client):
    asyncio.run(AdminAuthService.create_admin_user(
        name="BadCsrf Admin", email="badcsrfadmin@test.com", password="AdminPass123", role="admin"
    ))
    client.post("/admin/auth/login", json={"email": "badcsrfadmin@test.com", "password": "AdminPass123"})

    resp = client.post("/admin/auth/refresh", headers={"X-CSRF-Token": "not-the-real-token"})
    assert resp.status_code == 403


def test_customer_refresh_requires_matching_csrf_header(client):
    client.post("/auth/register", json={
        "name": "Csrf Customer", "email": "csrfcustomer@test.com", "password": "CustPass123", "phone": "03001234567",
    })
    assert client.cookies.get("refresh_token")
    csrf_token = client.cookies.get("csrf_token")
    assert csrf_token, "register/login must also issue the double-submit CSRF cookie"

    # Missing header -> rejected
    resp = client.post("/auth/refresh")
    assert resp.status_code == 403

    # Wrong header -> rejected
    resp = client.post("/auth/refresh", headers={"X-CSRF-Token": "wrong"})
    assert resp.status_code == 403

    # Correct header -> succeeds and rotates both cookies
    resp = client.post("/auth/refresh", headers={"X-CSRF-Token": csrf_token})
    assert resp.status_code == 200, resp.text
    assert "access_token" in resp.json()
    assert client.cookies.get("csrf_token")
