"""
Regression tests for NOTES_schema_audit.md §9 (task 9): data-integrity fixes around checkout
atomicity, revenue aggregation, and timestamp standardization.
"""
import asyncio

from services.admin_auth import AdminAuthService
from services.dashboard import DashboardService


def _admin_token(client, email="integrity@test.com", password="AdminPass123"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role="admin"))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


def _register_customer(client, email="integritybuyer@test.com", password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "Buyer", "email": email, "password": password, "phone": "03001234567",
    })
    return resp.json()["access_token"]


def _create_product(client, admin_token, stock=10):
    resp = client.post(
        "/admin/products",
        json={
            "name": "Integrity Test Shirt", "description": "shirt", "category": "t-shirts",
            "price": 1000, "discount_percentage": 0, "tags": [], "images": [],
            "variants": [{"size": "M", "color": "Red", "sku": "integrity-m-red", "stock": stock}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return resp.json()["data"]["product_id"]


def test_invalid_promo_code_does_not_leave_stock_permanently_decremented(client):
    """A promo code rejected *after* stock was already decremented for earlier items in the
    same order must not leave that stock burned with no order to show for it — the whole
    request (item loop + promo + order insert) is one unit now (see routes/orders.py::place_order
    and utils/db_transaction.py)."""
    admin_token = _admin_token(client)
    customer_token = _register_customer(client)
    product_id = _create_product(client, admin_token, stock=10)

    order_resp = client.post(
        "/orders",
        json={
            "items": [{
                "product_id": product_id, "name": "Integrity Test Shirt", "price": 1000,
                "quantity": 3, "size": "M", "color": "Red", "image": "",
            }],
            "shipping_address": {
                "full_name": "Buyer", "phone": "03001234567",
                "address": "1 Test Rd", "city": "Karachi", "postal_code": "75000",
            },
            "payment_method": "cod",
            "promo_code": "DOES-NOT-EXIST",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert order_resp.status_code == 400

    detail = client.get(f"/products/{product_id}").json()
    variant = detail["variants"][0]
    assert variant["stock"] == 10, "stock was decremented for an order that was ultimately rejected"
    assert detail["total_stock"] == 10


def test_cancelled_orders_excluded_from_admin_revenue_totals(client):
    admin_token = _admin_token(client)
    customer_token = _register_customer(client)
    product_id = _create_product(client, admin_token, stock=10)

    def place_order():
        resp = client.post(
            "/orders",
            json={
                "items": [{
                    "product_id": product_id, "name": "Integrity Test Shirt", "price": 1000,
                    "quantity": 1, "size": "M", "color": "Red", "image": "",
                }],
                "shipping_address": {
                    "full_name": "Buyer", "phone": "03001234567",
                    "address": "1 Test Rd", "city": "Karachi", "postal_code": "75000",
                },
                "payment_method": "cod",
            },
            headers={"Authorization": f"Bearer {customer_token}"},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()

    kept_order = place_order()
    cancelled_order = place_order()

    cancel_resp = client.post(
        f"/orders/{cancelled_order['id']}/cancel",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert cancel_resp.status_code == 200, cancel_resp.text

    stats = client.get("/admin/stats", headers={"Authorization": f"Bearer {admin_token}"})
    assert stats.status_code == 200, stats.text
    # Only the kept (pending) order's total should count toward revenue — the cancelled one must
    # not inflate it, whether "gross" or "net" is the intended semantic (see NOTES_schema_audit.md §9).
    assert stats.json()["total_revenue"] == kept_order["total"]


def test_dashboard_orders_today_query_matches_native_datetime_created_at(client):
    """Regression test for NOTES_schema_audit.md §9's timestamp standardization: routes/orders.py
    used to store `created_at` as an ISO string while services/dashboard.py queried it with a
    native datetime `{"$gte": ...}` filter — a BSON string never matches a datetime comparison,
    so `orders_today`/`revenue_today` silently returned 0 no matter how many orders were placed
    today. Both sides now agree on native BSON datetime."""
    admin_token = _admin_token(client)
    customer_token = _register_customer(client)
    product_id = _create_product(client, admin_token, stock=5)

    order_resp = client.post(
        "/orders",
        json={
            "items": [{
                "product_id": product_id, "name": "Integrity Test Shirt", "price": 1000,
                "quantity": 1, "size": "M", "color": "Red", "image": "",
            }],
            "shipping_address": {
                "full_name": "Buyer", "phone": "03001234567",
                "address": "1 Test Rd", "city": "Karachi", "postal_code": "75000",
            },
            "payment_method": "cod",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert order_resp.status_code == 200, order_resp.text

    async def _fetch_stats():
        from database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            return await DashboardService.get_dashboard_stats(db)

    stats = asyncio.run(_fetch_stats())
    assert stats["orders_today"] >= 1
