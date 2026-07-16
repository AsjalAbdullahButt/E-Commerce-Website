"""
Fills the remaining gaps in routes/admin.py coverage found in the full route-inventory audit:
GET/DELETE /admin/products/{id}, GET /admin/products (admin list) and /products/low-stock/items,
GET /admin/inventory/history/{id}, GET /admin/orders/{id}, GET /admin/users/{id} and
/admin/users/{id}/orders, POST /admin/users/{id}/unban, and the admin auth extras
(logout/change-password/unlock) had no dedicated tests before this file.
"""
import asyncio

from services.admin_auth import AdminAuthService


def _admin_token(client, email="remainingadmin@test.com", password="AdminPass123", role="admin"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role=role))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


def _register_customer(client, email="remainingcustomer@test.com", password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "Remaining Routes Customer", "email": email, "password": password, "phone": "03001234567",
    })
    return resp.json()["access_token"]


def _create_product(client, admin_token, sku="remaining-item"):
    resp = client.post(
        "/admin/products",
        json={
            "name": "Remaining Routes Item", "description": "test", "category": "accessories",
            "price": 300, "discount_percentage": 0, "tags": [], "images": [],
            "variants": [{"size": "One Size", "color": "Blue", "sku": sku, "stock": 3}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["product_id"]


# ── Products ─────────────────────────────────────────────────────────────────

def test_admin_get_list_and_delete_product(client):
    admin_token = _admin_token(client)
    headers = {"Authorization": f"Bearer {admin_token}"}
    product_id = _create_product(client, admin_token)

    get_resp = client.get(f"/admin/products/{product_id}", headers=headers)
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["data"]["name"] == "Remaining Routes Item"

    list_resp = client.get("/admin/products", headers=headers)
    assert list_resp.status_code == 200
    assert any(p["id"] == product_id for p in list_resp.json()["data"])

    # product:delete is super_admin-only in utils/permissions.py — plain "admin" is rejected.
    delete_forbidden = client.delete(f"/admin/products/{product_id}", headers=headers)
    assert delete_forbidden.status_code == 403

    super_admin_token = _admin_token(client, email="remainingsuperadmin@test.com", role="super_admin")
    delete_resp = client.delete(
        f"/admin/products/{product_id}",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert delete_resp.status_code == 200, delete_resp.text


def test_admin_low_stock_items_reachable(client):
    admin_token = _admin_token(client, email="remainingadmin2@test.com")
    _create_product(client, admin_token, sku="remaining-item-2")  # stock=3, likely under any reasonable threshold

    resp = client.get("/admin/products/low-stock/items", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200, resp.text
    assert "data" in resp.json()


def test_admin_inventory_history_reachable(client):
    admin_token = _admin_token(client, email="remainingadmin3@test.com")
    product_id = _create_product(client, admin_token, sku="remaining-item-3")

    client.post(
        "/admin/inventory/adjust-stock",
        params={"product_id": product_id, "variant_sku": "remaining-item-3", "quantity_change": 5, "reason": "restock"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    resp = client.get(f"/admin/inventory/history/{product_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200, resp.text


# ── Orders ───────────────────────────────────────────────────────────────────

def test_admin_get_single_order(client):
    admin_token = _admin_token(client, email="remainingadmin4@test.com")
    customer_token = _register_customer(client, email="remainingcustomer2@test.com")
    product_id = _create_product(client, admin_token, sku="remaining-item-4")

    order_resp = client.post(
        "/orders",
        json={
            "items": [{"product_id": product_id, "name": "x", "price": 300, "quantity": 1, "size": "One Size", "color": "Blue", "image": ""}],
            "shipping_address": {"full_name": "x", "phone": "03001234567", "address": "1 Test Rd", "city": "Karachi", "postal_code": "75000"},
            "payment_method": "cod",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    order_id = order_resp.json()["id"]

    resp = client.get(f"/admin/orders/{order_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200, resp.text


# ── Users ────────────────────────────────────────────────────────────────────

def test_admin_get_user_and_their_orders(client):
    admin_token = _admin_token(client, email="remainingadmin5@test.com")
    customer_token = _register_customer(client, email="remainingcustomer3@test.com")
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {customer_token}"}).json()

    get_resp = client.get(f"/admin/users/{me['id']}", headers={"Authorization": f"Bearer {admin_token}"})
    assert get_resp.status_code == 200, get_resp.text

    orders_resp = client.get(f"/admin/users/{me['id']}/orders", headers={"Authorization": f"Bearer {admin_token}"})
    assert orders_resp.status_code == 200, orders_resp.text


def test_admin_unban_user(client):
    """super_admin has user:ban (utils/permissions.py) — ban then unban round-trip."""
    super_admin_token = _admin_token(client, email="remainingsuperadmin2@test.com", role="super_admin")
    customer_token = _register_customer(client, email="remainingcustomer4@test.com")
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {customer_token}"}).json()
    headers = {"Authorization": f"Bearer {super_admin_token}"}

    ban_resp = client.post(f"/admin/users/{me['id']}/ban", params={"reason": "test ban"}, headers=headers)
    assert ban_resp.status_code == 200, ban_resp.text
    assert ban_resp.json()["data"]["is_banned"] is True

    unban_resp = client.post(f"/admin/users/{me['id']}/unban", headers=headers)
    assert unban_resp.status_code == 200, unban_resp.text
    assert unban_resp.json()["data"]["is_banned"] is False


# ── Admin auth extras ────────────────────────────────────────────────────────

def test_admin_logout_clears_cookie(client):
    email, password = "remainingadmin6@test.com", "AdminPass123"
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role="admin"))
    login_resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    token = login_resp.json()["data"]["access_token"]
    assert client.cookies.get("admin_refresh_token")

    resp = client.post("/admin/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    assert client.cookies.get("admin_refresh_token") is None


def test_admin_change_password_success_and_relogin(client):
    email = "remainingadmin7@test.com"
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password="OldPass123", role="admin"))
    login_resp = client.post("/admin/auth/login", json={"email": email, "password": "OldPass123"})
    token = login_resp.json()["data"]["access_token"]

    resp = client.post(
        "/admin/auth/change-password",
        json={"old_password": "OldPass123", "new_password": "NewPass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text

    old_login = client.post("/admin/auth/login", json={"email": email, "password": "OldPass123"})
    assert old_login.status_code == 401

    new_login = client.post("/admin/auth/login", json={"email": email, "password": "NewPass456"})
    assert new_login.status_code == 200


def test_super_admin_can_unlock_locked_admin_account(client):
    email, password = "lockme@test.com", "AdminPass123"
    asyncio.run(AdminAuthService.create_admin_user(name="Lockable Admin", email=email, password=password, role="admin"))

    for _ in range(5):
        client.post("/admin/auth/login", json={"email": email, "password": "WrongPassword1"})

    locked_login = client.post("/admin/auth/login", json={"email": email, "password": password})
    assert locked_login.status_code == 423  # Locked — AdminAuthService.authenticate's explicit signal

    async def _fetch_locked_admin():
        from sqlalchemy import select
        from database import AsyncSessionLocal
        from db.admin import AdminUser
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(AdminUser).where(AdminUser.email == email))
            return result.scalar_one()

    locked_admin = asyncio.run(_fetch_locked_admin())
    assert locked_admin.is_locked is True

    super_admin_token = _admin_token(client, email="remainingsuperadmin3@test.com", role="super_admin")
    unlock_resp = client.post(
        f"/admin/auth/unlock/{locked_admin.id}",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert unlock_resp.status_code == 200, unlock_resp.text

    unlocked_login = client.post("/admin/auth/login", json={"email": email, "password": password})
    assert unlocked_login.status_code == 200


def test_plain_admin_cannot_unlock_account(client):
    """admin:update is super_admin-only in utils/permissions.py."""
    admin_token = _admin_token(client, email="remainingadmin8@test.com")
    resp = client.post(
        "/admin/auth/unlock/000000000000000000000000",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 403
