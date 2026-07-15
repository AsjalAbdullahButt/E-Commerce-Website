"""
Regression test for the products/orders schema-divergence bug described in
NOTES_schema_audit.md §1 and §3: a product created exactly the way the real admin UI creates it
(variants[] payload, POST /admin/products) must be purchasable through the real customer checkout
endpoint (POST /orders), with the correct variant's stock atomically decremented.

Before the fix, POST /admin/products wrote `variants[]`/`total_stock` documents while
POST /orders' stock decrement only matched a top-level `stock` field — so this exact path always
failed with "Stock was just taken ... please refresh" regardless of actual stock.
"""
import asyncio

from services.admin_auth import AdminAuthService


def _create_admin(email="admin@test.com", password="AdminPass123", role="admin"):
    return asyncio.run(
        AdminAuthService.create_admin_user(name="Test Admin", email=email, password=password, role=role)
    )


def _admin_token(client, email="admin@test.com", password="AdminPass123"):
    _create_admin(email=email, password=password)
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _register_customer(client, email="shopper@test.com", password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "Shopper",
        "email": email,
        "password": password,
        "phone": "03001234567",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


PRODUCT_PAYLOAD = {
    "name": "Test Hoodie",
    "description": "A hoodie for testing",
    "category": "hoodies",
    "price": 3000,
    "discount_percentage": 0,
    "tags": ["test"],
    "images": ["https://example.com/hoodie.jpg"],
    "variants": [
        {"size": "M", "color": "Black", "sku": "hoodie-m-black", "stock": 10},
        {"size": "L", "color": "Black", "sku": "hoodie-l-black", "stock": 5},
    ],
}


def test_product_created_via_admin_ui_shape_is_purchasable_and_decrements_stock(client):
    admin_token = _admin_token(client)

    # 1. Admin creates a product exactly the way frontend/admin/js/products.js does.
    create_resp = client.post(
        "/admin/products",
        json=PRODUCT_PAYLOAD,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_resp.status_code == 200, create_resp.text
    product_id = create_resp.json()["data"]["product_id"]

    # 2. Customer sees it in the shop via the real public read path.
    shop_resp = client.get("/products")
    assert shop_resp.status_code == 200, shop_resp.text
    listed_ids = [p["id"] for p in shop_resp.json()["products"]]
    assert product_id in listed_ids

    detail_resp = client.get(f"/products/{product_id}")
    assert detail_resp.status_code == 200, detail_resp.text
    product = detail_resp.json()
    assert product["total_stock"] == 15
    m_variant = next(v for v in product["variants"] if v["size"] == "M" and v["color"] == "Black")
    assert m_variant["stock"] == 10

    # 3. Customer registers, logs in, and buys 3 units of the M/Black variant.
    customer_token = _register_customer(client)
    order_resp = client.post(
        "/orders",
        json={
            "items": [{
                "product_id": product_id,
                "name": "Test Hoodie",
                "price": 3000,
                "quantity": 3,
                "size": "M",
                "color": "Black",
                "image": "https://example.com/hoodie.jpg",
            }],
            "shipping_address": {
                "full_name": "Shopper",
                "phone": "03001234567",
                "address": "123 Test St",
                "city": "Karachi",
                "postal_code": "75000",
            },
            "payment_method": "cod",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert order_resp.status_code == 200, order_resp.text
    order = order_resp.json()
    assert order["status"] == "pending"
    assert order["total"] > 0
    order_id = order["id"]

    # 4. Stock actually decremented — the exact scenario that used to always 400.
    detail_after = client.get(f"/products/{product_id}").json()
    m_after = next(v for v in detail_after["variants"] if v["size"] == "M" and v["color"] == "Black")
    l_after = next(v for v in detail_after["variants"] if v["size"] == "L" and v["color"] == "Black")
    assert m_after["stock"] == 7          # 10 - 3
    assert l_after["stock"] == 5          # untouched
    assert detail_after["total_stock"] == 12

    # 5. Order shows up in the customer's own order history...
    my_orders = client.get("/orders/me", headers={"Authorization": f"Bearer {customer_token}"})
    assert my_orders.status_code == 200
    assert order_id in [o["id"] for o in my_orders.json()["data"]]

    # 6. ...AND in the admin orders list (validates OrderService no longer filters on the
    #    legacy is_deleted field, which the real checkout path never sets).
    admin_orders = client.get("/admin/orders", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_orders.status_code == 200, admin_orders.text
    admin_order_ids = [o["id"] for o in admin_orders.json()["data"]]
    assert order_id in admin_order_ids


def test_insufficient_stock_returns_400_and_does_not_partially_decrement(client):
    admin_token = _admin_token(client)
    create_resp = client.post(
        "/admin/products",
        json=PRODUCT_PAYLOAD,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    product_id = create_resp.json()["data"]["product_id"]
    customer_token = _register_customer(client)

    order_resp = client.post(
        "/orders",
        json={
            "items": [{
                "product_id": product_id,
                "name": "Test Hoodie",
                "price": 3000,
                "quantity": 11,  # only 10 in stock for M/Black
                "size": "M",
                "color": "Black",
                "image": "",
            }],
            "shipping_address": {
                "full_name": "Shopper", "phone": "03001234567",
                "address": "123 Test St", "city": "Karachi", "postal_code": "75000",
            },
            "payment_method": "cod",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert order_resp.status_code == 400

    detail = client.get(f"/products/{product_id}").json()
    m_variant = next(v for v in detail["variants"] if v["size"] == "M" and v["color"] == "Black")
    assert m_variant["stock"] == 10  # untouched
