"""Tests for CSV product/order export+import (services/csv_io.py) and the Excel sales/inventory
report (services/reports.py, extends services/dashboard.py rather than duplicating its queries).
"""
import asyncio
import io

from services.admin_auth import AdminAuthService


def _admin_token(client, email="csvadmin@test.com", password="AdminPass123", role="admin"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role=role))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


def _register_customer(client, email="csvcustomer@test.com", password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "CSV Customer", "email": email, "password": password, "phone": "03001234567",
    })
    return resp.json()["access_token"]


def _create_product(client, admin_token, sku="csv-item", name="CSV Item"):
    resp = client.post(
        "/admin/products",
        json={
            "name": name, "description": "test", "category": "accessories",
            "price": 500, "discount_percentage": 0, "tags": ["a"], "images": [],
            "variants": [{"size": "One Size", "color": "Black", "sku": sku, "stock": 15}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return resp.json()["data"]["product_id"]


def _place_order(client, customer_token, product_id):
    resp = client.post(
        "/orders",
        json={
            "items": [{
                "product_id": product_id, "name": "x", "price": 500,
                "quantity": 1, "size": "One Size", "color": "Black", "image": "",
            }],
            "shipping_address": {
                "full_name": "CSV Customer", "phone": "03001234567",
                "address": "1 CSV Rd", "city": "Karachi", "postal_code": "75000",
            },
            "payment_method": "cod",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _upload_csv(client, admin_token, path, csv_text, filename="import.csv"):
    return client.post(
        path,
        files={"file": (filename, io.BytesIO(csv_text.encode()), "text/csv")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )


# ── Products export/import ───────────────────────────────────────────────

def test_export_products_csv(client):
    admin_token = _admin_token(client)
    _create_product(client, admin_token, sku="csv-item-1", name="Exported Item")

    resp = client.get("/admin/products/export", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    assert "Exported Item" in resp.text
    assert resp.text.splitlines()[0].startswith("product_name,")


def test_import_products_creates_new_product(client):
    admin_token = _admin_token(client, email="csvadmin2@test.com")
    csv_text = (
        "product_name,description,category,price,discount_percentage,tags,image_url,is_active,size,color,sku,stock\n"
        "Imported Shirt,A nice shirt,t-shirts,1200,10,summer;new,,true,M,Blue,imported-shirt-m-blue,20\n"
        "Imported Shirt,A nice shirt,t-shirts,1200,10,summer;new,,true,L,Blue,imported-shirt-l-blue,15\n"
    )
    resp = _upload_csv(client, admin_token, "/admin/products/import", csv_text)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["created"] == 1
    assert data["updated"] == 0
    assert data["errors"] == []

    list_resp = client.get("/products?search=Imported Shirt")
    products = list_resp.json()["products"]
    assert any(p["name"] == "Imported Shirt" for p in products)
    imported = next(p for p in products if p["name"] == "Imported Shirt")
    assert len(imported["variants"]) == 2


def test_import_products_updates_existing_product(client):
    admin_token = _admin_token(client, email="csvadmin3@test.com")
    _create_product(client, admin_token, sku="csv-item-3", name="Update Me")

    csv_text = (
        "product_name,description,category,price,discount_percentage,tags,image_url,is_active,size,color,sku,stock\n"
        "Update Me,test,accessories,999,5,,,true,One Size,Black,csv-item-3,50\n"
    )
    resp = _upload_csv(client, admin_token, "/admin/products/import", csv_text)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["created"] == 0
    assert data["updated"] == 1

    list_resp = client.get("/products?search=Update Me")
    updated = next(p for p in list_resp.json()["products"] if p["name"] == "Update Me")
    assert updated["price"] == 999
    assert updated["variants"][0]["stock"] == 50


def test_import_products_reports_row_errors_without_aborting_good_rows(client):
    admin_token = _admin_token(client, email="csvadmin4@test.com")
    csv_text = (
        "product_name,description,category,price,discount_percentage,tags,image_url,is_active,size,color,sku,stock\n"
        "Bad Row Product,test,accessories,not-a-number,0,,,true,One Size,Black,bad-row-sku,5\n"
        "Good Row Product,test,accessories,700,0,,,true,One Size,Black,good-row-sku,5\n"
    )
    resp = _upload_csv(client, admin_token, "/admin/products/import", csv_text)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["created"] == 1
    assert len(data["errors"]) == 1

    list_resp = client.get("/products?search=Good Row Product")
    assert any(p["name"] == "Good Row Product" for p in list_resp.json()["products"])


def test_import_products_requires_permission(client):
    support_token = _admin_token(client, email="csvsupport@test.com", role="support")
    csv_text = "product_name,description,category,price,discount_percentage,tags,image_url,is_active,size,color,sku,stock\n"
    resp = _upload_csv(client, support_token, "/admin/products/import", csv_text)
    assert resp.status_code == 403


# ── Orders export / bulk status update ──────────────────────────────────

def test_export_orders_csv(client):
    admin_token = _admin_token(client, email="csvadmin5@test.com")
    customer_token = _register_customer(client, email="csvcustomer5@test.com")
    product_id = _create_product(client, admin_token, sku="csv-item-5")
    order = _place_order(client, customer_token, product_id)

    resp = client.get("/admin/orders/export", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    assert order["id"] in resp.text


def test_bulk_update_order_status(client):
    admin_token = _admin_token(client, email="csvadmin6@test.com")
    customer_token = _register_customer(client, email="csvcustomer6@test.com")
    product_id = _create_product(client, admin_token, sku="csv-item-6")
    order = _place_order(client, customer_token, product_id)

    csv_text = f"order_id,status,note\n{order['id']},confirmed,Bulk confirmed\n"
    resp = _upload_csv(client, admin_token, "/admin/orders/bulk-status-update", csv_text)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["updated"] == 1
    assert data["errors"] == []

    order_resp = client.get(f"/orders/{order['id']}", headers={"Authorization": f"Bearer {admin_token}"})
    assert order_resp.json()["status"] == "confirmed"


def test_bulk_update_order_status_reports_invalid_transition(client):
    admin_token = _admin_token(client, email="csvadmin7@test.com")
    customer_token = _register_customer(client, email="csvcustomer7@test.com")
    product_id = _create_product(client, admin_token, sku="csv-item-7a")
    good_order = _place_order(client, customer_token, product_id)
    product_id_2 = _create_product(client, admin_token, sku="csv-item-7b")
    bad_order = _place_order(client, customer_token, product_id_2)

    # pending -> delivered directly is an invalid transition; pending -> confirmed is valid.
    csv_text = (
        f"order_id,status,note\n"
        f"{bad_order['id']},delivered,Invalid jump\n"
        f"{good_order['id']},confirmed,Valid transition\n"
    )
    resp = _upload_csv(client, admin_token, "/admin/orders/bulk-status-update", csv_text)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["updated"] == 1
    assert len(data["errors"]) == 1

    good_resp = client.get(f"/orders/{good_order['id']}", headers={"Authorization": f"Bearer {admin_token}"})
    assert good_resp.json()["status"] == "confirmed"
    bad_resp = client.get(f"/orders/{bad_order['id']}", headers={"Authorization": f"Bearer {admin_token}"})
    assert bad_resp.json()["status"] == "pending"  # unchanged


# ── Sales/inventory report ───────────────────────────────────────────────

def test_sales_inventory_report_downloads_valid_xlsx(client):
    admin_token = _admin_token(client, email="csvadmin8@test.com")
    resp = client.get("/admin/reports/sales-inventory", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert resp.content.startswith(b"PK")  # xlsx is a zip archive
    assert "sales-inventory-report.xlsx" in resp.headers["content-disposition"]


def test_reports_requires_permission(client):
    resp = client.get("/admin/reports/sales-inventory")  # no auth at all
    assert resp.status_code == 401
