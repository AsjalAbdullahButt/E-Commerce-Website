"""Phase 5 item 5: GET /products/{id}/recommendations -- "frequently bought together" from
OrderItem co-occurrence (routes/products.py::get_recommendations). A single self-join + GROUP BY
over order_items, ranked by how often each other product appeared in the same order as this one.
"""
import asyncio

from services.admin_auth import AdminAuthService


def _admin_token(client, email="recoadmin@test.com", password="AdminPass123"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role="admin"))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


def _register_customer(client, email, password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "Reco Customer", "email": email, "password": password, "phone": "03001234567",
    })
    return resp.json()["access_token"]


def _create_product(client, admin_token, name, sku, stock=50):
    resp = client.post(
        "/admin/products",
        json={
            "name": name, "description": "test", "category": "accessories",
            "price": 500, "discount_percentage": 0, "tags": [], "images": [],
            "variants": [{"size": "One Size", "color": "Black", "sku": sku, "stock": stock}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["product_id"]


def _place_order(client, customer_token, product_ids):
    resp = client.post(
        "/orders",
        json={
            "items": [
                {"product_id": pid, "name": "x", "price": 500, "quantity": 1, "size": "One Size", "color": "Black", "image": ""}
                for pid in product_ids
            ],
            "shipping_address": {
                "full_name": "Reco Customer", "phone": "03001234567",
                "address": "1 Test Rd", "city": "Karachi", "postal_code": "75000",
            },
            "payment_method": "cod",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def test_recommendations_rank_by_co_occurrence(client):
    admin_token = _admin_token(client)
    product_a = _create_product(client, admin_token, "Reco Anchor", "reco-a")
    product_b = _create_product(client, admin_token, "Reco Frequent Pair", "reco-b")
    product_c = _create_product(client, admin_token, "Reco Rare Pair", "reco-c")
    product_d = _create_product(client, admin_token, "Reco Unrelated", "reco-d")

    # A+B bought together twice, A+C bought together once, D never with A.
    _place_order(client, _register_customer(client, "reco1@test.com"), [product_a, product_b])
    _place_order(client, _register_customer(client, "reco2@test.com"), [product_a, product_b])
    _place_order(client, _register_customer(client, "reco3@test.com"), [product_a, product_c])
    _place_order(client, _register_customer(client, "reco4@test.com"), [product_d])

    resp = client.get(f"/products/{product_a}/recommendations")
    assert resp.status_code == 200, resp.text
    ids = [p["id"] for p in resp.json()["products"]]

    assert ids[0] == product_b  # highest co-occurrence count (2) ranks first
    assert product_c in ids
    assert product_d not in ids  # never co-purchased with A
    assert product_a not in ids  # never recommends the product itself


def test_recommendations_empty_for_product_never_purchased(client):
    admin_token = _admin_token(client)
    lonely_product = _create_product(client, admin_token, "Never Purchased", "reco-lonely")

    resp = client.get(f"/products/{lonely_product}/recommendations")
    assert resp.status_code == 200, resp.text
    assert resp.json()["products"] == []


def test_recommendations_excludes_inactive_products(client):
    admin_token = _admin_token(client)
    product_a = _create_product(client, admin_token, "Reco Active Anchor", "reco-e")
    product_b = _create_product(client, admin_token, "Reco Soon Inactive", "reco-f")

    _place_order(client, _register_customer(client, "reco5@test.com"), [product_a, product_b])

    deactivate_resp = client.put(
        f"/admin/products/{product_b}", json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert deactivate_resp.status_code == 200, deactivate_resp.text

    resp = client.get(f"/products/{product_a}/recommendations")
    assert resp.status_code == 200, resp.text
    ids = [p["id"] for p in resp.json()["products"]]
    assert product_b not in ids


def test_recommendations_rejects_invalid_product_id(client):
    resp = client.get("/products/not-a-valid-id/recommendations")
    assert resp.status_code == 400
