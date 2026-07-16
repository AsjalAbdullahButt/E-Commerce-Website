"""
routes/promos.py had zero test coverage before this file (confirmed via grep across the whole
tests/ tree). Covers the customer-facing promo-code validation flow (POST /promos/validate) and
the admin-side CRUD (POST/GET/DELETE /promos) — a separate, parallel path from
/admin/discounts::DiscountService (see NOTES_schema_audit.md §8: both write compatible fields to
promos_col but are independently maintained code paths, by design, not a bug).
"""
import asyncio
from datetime import datetime, timedelta

from services.admin_auth import AdminAuthService


def _admin_token(client, email="promoadmin@test.com", password="AdminPass123"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role="admin"))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


def _register_customer(client, email="promocustomer@test.com", password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "Promo Customer", "email": email, "password": password, "phone": "03001234567",
    })
    return resp.json()["access_token"]


def test_non_admin_cannot_create_promo(client):
    customer_token = _register_customer(client)
    resp = client.post(
        "/promos",
        json={"code": "NOPE10", "discount_type": "percentage", "discount_value": 10},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 403


def test_admin_create_list_delete_promo(client):
    admin_token = _admin_token(client)
    headers = {"Authorization": f"Bearer {admin_token}"}

    create_resp = client.post(
        "/promos",
        json={"code": "save15", "discount_type": "percentage", "discount_value": 15, "min_order": 500, "max_uses": 10},
        headers=headers,
    )
    assert create_resp.status_code == 200, create_resp.text

    # Code is upper-cased server-side regardless of input casing.
    list_resp = client.get("/promos", headers=headers)
    assert list_resp.status_code == 200
    codes = [p["code"] for p in list_resp.json()]
    assert "SAVE15" in codes
    promo_id = next(p["id"] for p in list_resp.json() if p["code"] == "SAVE15")

    # Duplicate code is rejected.
    dup_resp = client.post(
        "/promos",
        json={"code": "SAVE15", "discount_type": "fixed", "discount_value": 5},
        headers=headers,
    )
    assert dup_resp.status_code == 400

    del_resp = client.delete(f"/promos/{promo_id}", headers=headers)
    assert del_resp.status_code == 200

    list_after = client.get("/promos", headers=headers)
    assert "SAVE15" not in [p["code"] for p in list_after.json()]


def test_delete_promo_with_invalid_id_rejected(client):
    admin_token = _admin_token(client, email="promoadmin2@test.com")
    resp = client.delete("/promos/not-a-valid-id", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 400


def test_validate_promo_success(client):
    admin_token = _admin_token(client, email="promoadmin3@test.com")
    customer_token = _register_customer(client, email="promocustomer3@test.com")

    client.post(
        "/promos",
        json={"code": "TENOFF", "discount_type": "percentage", "discount_value": 10, "min_order": 100, "max_uses": 5},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    resp = client.post(
        "/promos/validate",
        json={"code": "tenoff", "order_total": 1000},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["valid"] is True
    assert body["discount_amount"] == 100.0
    assert body["code"] == "TENOFF"


def test_validate_promo_below_minimum_order_rejected(client):
    admin_token = _admin_token(client, email="promoadmin4@test.com")
    customer_token = _register_customer(client, email="promocustomer4@test.com")

    client.post(
        "/promos",
        json={"code": "BIGORDER", "discount_type": "fixed", "discount_value": 50, "min_order": 5000},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    resp = client.post(
        "/promos/validate",
        json={"code": "BIGORDER", "order_total": 100},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 400


def test_validate_expired_promo_rejected(client):
    admin_token = _admin_token(client, email="promoadmin5@test.com")
    customer_token = _register_customer(client, email="promocustomer5@test.com")

    expired = (datetime.utcnow() - timedelta(days=1)).isoformat()
    client.post(
        "/promos",
        json={"code": "EXPIRED1", "discount_type": "percentage", "discount_value": 20, "expires_at": expired},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    resp = client.post(
        "/promos/validate",
        json={"code": "EXPIRED1", "order_total": 1000},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 400


def test_validate_nonexistent_promo_rejected(client):
    customer_token = _register_customer(client, email="promocustomer6@test.com")
    resp = client.post(
        "/promos/validate",
        json={"code": "DOESNOTEXIST", "order_total": 1000},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 404
