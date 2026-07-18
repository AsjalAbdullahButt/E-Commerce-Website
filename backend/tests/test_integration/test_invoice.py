"""Tests for GET /orders/{order_id}/invoice (services/invoice.py — reportlab PDF generation)."""
import asyncio

from services.admin_auth import AdminAuthService


def _admin_token(client, email="invoiceadmin@test.com", password="AdminPass123"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role="admin"))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


def _register_customer(client, email="invoicecustomer@test.com", password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "Invoice Customer", "email": email, "password": password, "phone": "03001234567",
    })
    return resp.json()["access_token"]


def _create_product(client, admin_token, sku="invoice-item"):
    resp = client.post(
        "/admin/products",
        json={
            "name": "Invoice Item", "description": "test", "category": "accessories",
            "price": 650, "discount_percentage": 0, "tags": [], "images": [],
            "variants": [{"size": "One Size", "color": "White", "sku": sku, "stock": 15}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return resp.json()["data"]["product_id"]


def _place_order(client, customer_token=None, product_id=None, guest_email=None):
    payload = {
        "items": [{
            "product_id": product_id, "name": "x", "price": 650,
            "quantity": 1, "size": "One Size", "color": "White", "image": "",
        }],
        "shipping_address": {
            "full_name": "Invoice Customer", "phone": "03001234567",
            "address": "1 Invoice Rd", "city": "Islamabad", "postal_code": "44000",
        },
        "payment_method": "cod",
    }
    if guest_email:
        payload["guest_email"] = guest_email
        resp = client.post("/orders", json=payload)
    else:
        resp = client.post("/orders", json=payload, headers={"Authorization": f"Bearer {customer_token}"})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_customer_can_download_own_invoice(client):
    admin_token = _admin_token(client)
    customer_token = _register_customer(client)
    product_id = _create_product(client, admin_token)
    order = _place_order(client, customer_token, product_id)

    resp = client.get(f"/orders/{order['id']}/invoice", headers={"Authorization": f"Bearer {customer_token}"})
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")
    assert f"invoice-{order['id'][:8]}.pdf" in resp.headers["content-disposition"]


def test_customer_cannot_download_another_customers_invoice(client):
    admin_token = _admin_token(client, email="invoiceadmin2@test.com")
    owner_token = _register_customer(client, email="invoiceowner@test.com")
    other_token = _register_customer(client, email="invoiceintruder@test.com")
    product_id = _create_product(client, admin_token, sku="invoice-item-2")
    order = _place_order(client, owner_token, product_id)

    resp = client.get(f"/orders/{order['id']}/invoice", headers={"Authorization": f"Bearer {other_token}"})
    assert resp.status_code == 403


def test_admin_can_download_any_invoice(client):
    admin_token = _admin_token(client, email="invoiceadmin3@test.com")
    customer_token = _register_customer(client, email="invoicecustomer3@test.com")
    product_id = _create_product(client, admin_token, sku="invoice-item-3")
    order = _place_order(client, customer_token, product_id)

    resp = client.get(f"/orders/{order['id']}/invoice", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200, resp.text
    assert resp.content.startswith(b"%PDF")


def test_guest_can_download_invoice_with_matching_email(client):
    admin_token = _admin_token(client, email="invoiceadmin4@test.com")
    product_id = _create_product(client, admin_token, sku="invoice-item-4")
    order = _place_order(client, product_id=product_id, guest_email="invoiceguest@test.com")

    resp = client.get(f"/orders/{order['id']}/invoice", params={"email": "invoiceguest@test.com"})
    assert resp.status_code == 200, resp.text
    assert resp.content.startswith(b"%PDF")


def test_guest_invoice_download_rejects_wrong_email(client):
    admin_token = _admin_token(client, email="invoiceadmin5@test.com")
    product_id = _create_product(client, admin_token, sku="invoice-item-5")
    order = _place_order(client, product_id=product_id, guest_email="invoiceguest2@test.com")

    resp = client.get(f"/orders/{order['id']}/invoice", params={"email": "wrong@test.com"})
    assert resp.status_code == 403


def test_invoice_rejects_invalid_order_id(client):
    customer_token = _register_customer(client, email="invoicecustomer6@test.com")
    resp = client.get("/orders/not-a-real-id/invoice", headers={"Authorization": f"Bearer {customer_token}"})
    assert resp.status_code == 400
