"""Tests for GET /sitemap.xml (routes/seo.py) — Phase 5 item 16."""
import asyncio

from services.admin_auth import AdminAuthService


def _admin_token(client, email="seoadmin@test.com", password="AdminPass123"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role="admin"))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


def test_sitemap_includes_static_pages(client):
    resp = client.get("/sitemap.xml")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/xml")
    body = resp.text
    assert "<urlset" in body
    assert "customer/index.html" in body
    assert "customer/shop.html" in body


def test_sitemap_includes_active_products_but_not_inactive(client):
    admin_token = _admin_token(client)
    active = client.post(
        "/admin/products",
        json={
            "name": "Sitemap Active Item", "description": "test", "category": "accessories",
            "price": 300, "discount_percentage": 0, "tags": [], "images": [],
            "variants": [{"size": "One Size", "color": "Black", "sku": "sitemap-active", "stock": 5}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    active_id = active.json()["data"]["product_id"]

    inactive = client.post(
        "/admin/products",
        json={
            "name": "Sitemap Inactive Item", "description": "test", "category": "accessories",
            "price": 300, "discount_percentage": 0, "tags": [], "images": [],
            "variants": [{"size": "One Size", "color": "Black", "sku": "sitemap-inactive", "stock": 5}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    inactive_id = inactive.json()["data"]["product_id"]
    client.put(f"/admin/products/{inactive_id}", json={"is_active": False}, headers={"Authorization": f"Bearer {admin_token}"})

    resp = client.get("/sitemap.xml")
    body = resp.text
    assert active_id in body
    assert inactive_id not in body


def test_sitemap_is_cached_across_requests(client):
    first = client.get("/sitemap.xml").text
    second = client.get("/sitemap.xml").text
    assert first == second
