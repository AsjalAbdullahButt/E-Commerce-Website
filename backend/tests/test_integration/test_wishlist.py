"""
routes/wishlist.py had zero test coverage before this file (confirmed via grep across the whole
tests/ tree). Covers add/list/remove and the idempotent-add / not-yet-added-remove edge cases.
"""
import asyncio

from services.admin_auth import AdminAuthService


def _admin_token(client, email="wishlistadmin@test.com", password="AdminPass123"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role="admin"))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


def _register_customer(client, email="wishlistcustomer@test.com", password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "Wishlist Customer", "email": email, "password": password, "phone": "03001234567",
    })
    return resp.json()["access_token"]


def _create_product(client, admin_token, name="Wishlist Test Item"):
    resp = client.post(
        "/admin/products",
        json={
            "name": name, "description": "test item", "category": "accessories",
            "price": 750, "discount_percentage": 0, "tags": [], "images": [],
            "variants": [{"size": "One Size", "color": "Black", "sku": f"wish-{name}", "stock": 5}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return resp.json()["data"]["product_id"]


def test_wishlist_starts_empty(client):
    customer_token = _register_customer(client)
    resp = client.get("/wishlist", headers={"Authorization": f"Bearer {customer_token}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_add_list_remove_wishlist_item(client):
    admin_token = _admin_token(client)
    customer_token = _register_customer(client, email="wishlistcustomer2@test.com")
    product_id = _create_product(client, admin_token)
    headers = {"Authorization": f"Bearer {customer_token}"}

    add_resp = client.post(f"/wishlist/{product_id}", headers=headers)
    assert add_resp.status_code == 200

    list_resp = client.get("/wishlist", headers=headers)
    assert list_resp.status_code == 200
    ids = [p["id"] for p in list_resp.json()]
    assert product_id in ids

    remove_resp = client.delete(f"/wishlist/{product_id}", headers=headers)
    assert remove_resp.status_code == 200

    list_after = client.get("/wishlist", headers=headers)
    assert product_id not in [p["id"] for p in list_after.json()]


def test_adding_same_product_twice_is_idempotent(client):
    admin_token = _admin_token(client, email="wishlistadmin3@test.com")
    customer_token = _register_customer(client, email="wishlistcustomer3@test.com")
    product_id = _create_product(client, admin_token, name="Idempotent Item")
    headers = {"Authorization": f"Bearer {customer_token}"}

    client.post(f"/wishlist/{product_id}", headers=headers)
    client.post(f"/wishlist/{product_id}", headers=headers)

    list_resp = client.get("/wishlist", headers=headers)
    ids = [p["id"] for p in list_resp.json()]
    assert ids.count(product_id) == 1


def test_remove_item_not_in_wishlist_is_a_no_op(client):
    customer_token = _register_customer(client, email="wishlistcustomer4@test.com")
    resp = client.delete("/wishlist/000000000000000000000000", headers={"Authorization": f"Bearer {customer_token}"})
    assert resp.status_code == 200


def test_wishlist_requires_auth(client):
    resp = client.get("/wishlist")
    assert resp.status_code in (401, 403)
