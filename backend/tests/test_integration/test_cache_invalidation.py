"""
Cache-bust confirmation test for NOTES_schema_audit.md §7 / task 6.

utils/cache.py has no Redis backend — it is a process-local dict, which only stays consistent
under the single-worker deployment this app now enforces at startup (main.py::
check_single_worker_deployment). Within that single process, an admin write MUST still correctly
invalidate the customer-facing product list/detail cache; this test proves that half of the
contract. Simulating a genuinely separate worker process (the other half — multiple processes
with their own independent memory) isn't meaningful to test in-process, since that's precisely the
gap the single-worker constraint exists to close instead of paper over.
"""
import asyncio

from services.admin_auth import AdminAuthService


def _admin_token(client, email="cacheadmin@test.com", password="AdminPass123"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role="admin"))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


def test_product_edit_busts_customer_facing_cache(client):
    admin_token = _admin_token(client)

    create_resp = client.post(
        "/admin/products",
        json={
            "name": "Cache Test Shirt", "description": "shirt", "category": "t-shirts",
            "price": 1000, "discount_percentage": 0, "tags": [], "images": [],
            "variants": [{"size": "M", "color": "Blue", "sku": "cache-m-blue", "stock": 10}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    product_id = create_resp.json()["data"]["product_id"]

    # Populate the cache via the real customer-facing read path.
    first_read = client.get(f"/products/{product_id}")
    assert first_read.status_code == 200
    assert first_read.json()["price"] == 1000

    list_before = client.get("/products")
    assert any(p["id"] == product_id and p["price"] == 1000 for p in list_before.json()["products"])

    # Admin edits the price — this must invalidate the cache the previous reads populated.
    update_resp = client.put(
        f"/admin/products/{product_id}",
        json={"price": 1500},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert update_resp.status_code == 200, update_resp.text

    second_read = client.get(f"/products/{product_id}")
    assert second_read.json()["price"] == 1500, "GET /products/{id} served a stale cached price after an admin edit"

    list_after = client.get("/products")
    assert any(p["id"] == product_id and p["price"] == 1500 for p in list_after.json()["products"]), \
        "GET /products served a stale cached list after an admin edit"
