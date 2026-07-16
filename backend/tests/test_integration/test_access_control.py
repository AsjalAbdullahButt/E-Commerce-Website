"""
Regression test for NOTES_schema_audit.md §5: routes/users.py used to duplicate
ban/unban/delete under /users/*, gated only by role membership (require_admin) rather than the
granular permission matrix — so a 'manager' or 'support' admin (neither of which has "user:ban"
in utils/permissions.py) could ban a user through that path even though /admin/users/*'s
permission check would have correctly rejected them. That duplicate router is now deleted, so
there is exactly one path — /admin/users/*/ban — and it must enforce the permission matrix.
"""
import asyncio

from services.admin_auth import AdminAuthService


def _admin_token(client, email, password, role):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role=role))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _register_customer(client, email="tobebanned@test.com", password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "Target", "email": email, "password": password, "phone": "03001234567",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["user"]["id"]


def test_duplicate_users_router_is_gone(client):
    resp = client.get("/users")
    assert resp.status_code == 404


def test_manager_without_user_ban_permission_is_rejected(client):
    manager_token = _admin_token(client, "mgr@test.com", "ManagerPass123", "manager")
    user_id = _register_customer(client)

    resp = client.post(
        f"/admin/users/{user_id}/ban",
        params={"reason": "test"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert resp.status_code == 403


def test_super_admin_with_user_ban_permission_can_ban(client):
    # Only super_admin has "user:ban" in utils/permissions.py — this is intentional (banning is
    # more sensitive than the read/update access "admin" gets), and is exactly the restriction
    # routes/users.py's role-membership-only check used to bypass for every admin sub-role.
    super_admin_token = _admin_token(client, "superadminban@test.com", "SuperAdminPass123", "super_admin")
    user_id = _register_customer(client, email="tobebanned2@test.com")

    resp = client.post(
        f"/admin/users/{user_id}/ban",
        params={"reason": "test"},
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["is_banned"] is True
