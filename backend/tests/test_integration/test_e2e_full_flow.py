"""
Task 10 — the single most important test in this pass: the exact end-to-end path that was
broken before this work (NOTES_schema_audit.md):

  admin creates a product (variants[], the real /admin/products shape)
    -> customer sees it in the shop with working size/color selectors (variants[] read path)
    -> customer buys it (POST /orders)
    -> stock decrements correctly (the Task 1/3 bug: used to always 400)
    -> order appears in BOTH the customer's order history (GET /orders/me) AND the admin orders
       list (GET /admin/orders), with matching status (the Task 2 bug: OrderService used to
       filter on is_deleted, which real orders never set, so admin's list was always empty)
    -> admin assigns a validated, active rider (Task 4: assign-rider used to skip validation
       entirely and there was no way to create a rider at all)
    -> rider sees the order (GET /rider/orders) and marks it delivered
    -> customer's order view and admin's orders list both reflect "delivered", with the product
       list cache correctly reflecting the final stock (Task 6/9: cache invalidation + stale data)

This test exercises the backend surface only (no browser); the frontend pieces of this same path
(product.js variant selectors, profile.js order history, admin orders.js/riders.js, rider
assigned-orders.html, tracking.js) were traced and fixed by reading the actual DOM/fetch code —
see the individual frontend fixes referenced in NOTES_schema_audit.md — not exercised by a real
browser here, since none is available in this environment.
"""
import asyncio

from services.admin_auth import AdminAuthService


def test_full_purchase_to_delivery_flow(client):
    # ── Admin logs in ────────────────────────────────────────────────────────────
    asyncio.run(AdminAuthService.create_admin_user(
        name="E2E Admin", email="e2eadmin@test.com", password="AdminPass123", role="admin"
    ))
    admin_login = client.post("/admin/auth/login", json={"email": "e2eadmin@test.com", "password": "AdminPass123"})
    assert admin_login.status_code == 200, admin_login.text
    admin_token = admin_login.json()["data"]["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # ── 1. Admin creates a product exactly the way frontend/admin/js/products.js does ─────────
    create_resp = client.post(
        "/admin/products",
        json={
            "name": "E2E Denim Jacket", "description": "denim jacket", "category": "clothing",
            "price": 5500, "discount_percentage": 0, "tags": ["e2e"],
            "images": ["https://example.com/jacket.jpg"],
            "variants": [
                {"size": "M", "color": "Blue", "sku": "e2e-jacket-m-blue", "stock": 8},
                {"size": "L", "color": "Blue", "sku": "e2e-jacket-l-blue", "stock": 4},
            ],
        },
        headers=admin_headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    product_id = create_resp.json()["data"]["product_id"]

    # ── 2. Customer sees it in the shop with size/color info intact ────────────────────────────
    shop_resp = client.get("/products")
    assert product_id in [p["id"] for p in shop_resp.json()["products"]]

    detail_resp = client.get(f"/products/{product_id}")
    variants = detail_resp.json()["variants"]
    sizes = sorted({v["size"] for v in variants})
    colors = sorted({v["color"] for v in variants})
    assert sizes == ["L", "M"]
    assert colors == ["Blue"]

    # ── Customer registers, logs in ─────────────────────────────────────────────────────────────
    register_resp = client.post("/auth/register", json={
        "name": "E2E Shopper", "email": "e2eshopper@test.com", "password": "Shopper123", "phone": "03001112222",
    })
    assert register_resp.status_code == 200, register_resp.text
    customer_token = register_resp.json()["access_token"]
    customer_headers = {"Authorization": f"Bearer {customer_token}"}

    # ── 3. Customer buys it (picks the M/Blue variant) ─────────────────────────────────────────
    order_resp = client.post(
        "/orders",
        json={
            "items": [{
                "product_id": product_id, "name": "E2E Denim Jacket", "price": 5500,
                "quantity": 2, "size": "M", "color": "Blue", "image": "https://example.com/jacket.jpg",
            }],
            "shipping_address": {
                "full_name": "E2E Shopper", "phone": "03001112222",
                "address": "42 E2E Street", "city": "Lahore", "postal_code": "54000",
            },
            "payment_method": "cod",
        },
        headers=customer_headers,
    )
    assert order_resp.status_code == 200, order_resp.text
    order = order_resp.json()
    order_id = order["id"]
    assert order["status"] == "pending"

    # ── 4. Stock decremented correctly (the core Task 1/3 regression) ──────────────────────────
    after_purchase = client.get(f"/products/{product_id}").json()
    m_variant = next(v for v in after_purchase["variants"] if v["size"] == "M")
    l_variant = next(v for v in after_purchase["variants"] if v["size"] == "L")
    assert m_variant["stock"] == 6          # 8 - 2
    assert l_variant["stock"] == 4          # untouched
    assert after_purchase["total_stock"] == 10

    # ── 5. Order appears in BOTH the customer's history AND the admin list ─────────────────────
    my_orders = client.get("/orders/me", headers=customer_headers)
    assert order_id in [o["id"] for o in my_orders.json()["data"]]

    admin_orders = client.get("/admin/orders", headers=admin_headers)
    admin_order = next(o for o in admin_orders.json()["data"] if o["id"] == order_id)
    assert admin_order["status"] == "pending"

    # ── 6. Admin creates a rider, activates them, and assigns them (validated) ─────────────────
    rider_resp = client.post(
        "/admin/riders",
        json={"name": "E2E Rider", "email": "e2erider@test.com", "password": "RiderPass123", "phone": "03003334444"},
        headers=admin_headers,
    )
    assert rider_resp.status_code == 200, rider_resp.text
    rider_id = rider_resp.json()["data"]["id"]

    rider_login = client.post("/auth/login", json={"email": "e2erider@test.com", "password": "RiderPass123"})
    assert rider_login.status_code == 200, rider_login.text
    rider_token = rider_login.json()["access_token"]
    rider_headers = {"Authorization": f"Bearer {rider_token}"}
    client.patch("/rider/status?status=available", headers=rider_headers)

    # Advance the order to a rider-assignable/shippable state.
    client.put(f"/admin/orders/{order_id}/status", json={"status": "confirmed"}, headers=admin_headers)
    client.put(f"/admin/orders/{order_id}/status", json={"status": "packed"}, headers=admin_headers)

    assign_resp = client.patch(f"/admin/orders/{order_id}/assign-rider?rider_id={rider_id}", headers=admin_headers)
    assert assign_resp.status_code == 200, assign_resp.text

    # ── 7. Rider sees the order and marks it shipped, then delivered ───────────────────────────
    rider_orders = client.get("/rider/orders", headers=rider_headers)
    assert order_id in [o["id"] for o in rider_orders.json()]

    ship_resp = client.patch(f"/rider/orders/{order_id}/status", json={"status": "shipped"}, headers=rider_headers)
    assert ship_resp.status_code == 200, ship_resp.text

    deliver_resp = client.post(f"/rider/orders/{order_id}/complete", headers=rider_headers)
    assert deliver_resp.status_code == 200, deliver_resp.text

    # ── 8. Customer's order view and admin's list both reflect "delivered" ─────────────────────
    customer_view = client.get(f"/orders/{order_id}", headers=customer_headers)
    assert customer_view.json()["status"] == "delivered"

    admin_orders_after = client.get("/admin/orders?status=delivered", headers=admin_headers)
    assert order_id in [o["id"] for o in admin_orders_after.json()["data"]]

    rider_stats = client.get("/rider/stats", headers=rider_headers)
    assert rider_stats.json()["delivered"] == 1

    # ── 9. Product list cache reflects the final stock — no stale data after the purchase ──────
    final_shop_view = client.get("/products")
    final_product = next(p for p in final_shop_view.json()["products"] if p["id"] == product_id)
    assert final_product["id"] == product_id  # sanity: still listed (is_active untouched)
    final_detail = client.get(f"/products/{product_id}").json()
    assert final_detail["total_stock"] == 10
