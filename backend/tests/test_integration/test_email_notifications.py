"""Tests for services/email.py (SendGrid REST send, dev-log fallback) and its wiring into order
confirmation, order status changes, and the low-stock admin alert. SendGrid is disabled by
default (no credentials in the test environment, mirroring .env.example) — most tests confirm
the "falls back to a logged audit entry, never raises" contract directly, the same way
test_forgot_password.py already does for the password-reset email. The one send-path test
monkeypatches httpx to avoid a real network call.
"""
import asyncio

import httpx
import pytest

import database
from config import settings
from db.admin import AuditLog
from services.email import EmailService
from services.admin_auth import AdminAuthService


def _latest_audit_entry(level: str, order_by_desc=True):
    async def _fetch():
        async with database.AsyncSessionLocal() as db:
            from sqlalchemy import select
            query = select(AuditLog).where(AuditLog.level == level).order_by(AuditLog.timestamp.desc())
            result = await db.execute(query)
            return result.scalars().first()

    return asyncio.run(_fetch())


def _count_audit_entries(level: str) -> int:
    async def _fetch():
        async with database.AsyncSessionLocal() as db:
            from sqlalchemy import func, select
            result = await db.execute(select(func.count()).select_from(AuditLog).where(AuditLog.level == level))
            return result.scalar_one()

    return asyncio.run(_fetch())


def _admin_token(client, email="emailadmin@test.com", password="AdminPass123", role="admin"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role=role))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


def _register_customer(client, email="emailcustomer@test.com", password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "Email Customer", "email": email, "password": password, "phone": "03001234567",
    })
    return resp.json()["access_token"]


def _create_product(client, admin_token, sku="email-item", stock=15):
    resp = client.post(
        "/admin/products",
        json={
            "name": "Email Item", "description": "test", "category": "accessories",
            "price": 500, "discount_percentage": 0, "tags": [], "images": [],
            "variants": [{"size": "One Size", "color": "Black", "sku": sku, "stock": stock}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return resp.json()["data"]["product_id"]


def _place_order(client, customer_token, product_id, quantity=1):
    resp = client.post(
        "/orders",
        json={
            "items": [{
                "product_id": product_id, "name": "x", "price": 500,
                "quantity": quantity, "size": "One Size", "color": "Black", "image": "",
            }],
            "shipping_address": {
                "full_name": "Email Customer", "phone": "03001234567",
                "address": "1 Test Rd", "city": "Karachi", "postal_code": "75000",
            },
            "payment_method": "cod",
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── EmailService itself ──────────────────────────────────────────────────

def test_email_send_falls_back_to_log_when_not_configured(client):
    result = asyncio.run(EmailService.send(
        "nobody@test.com", "Test Subject", "<p>hi</p>", event_code="TEST_EMAIL_EVENT",
    ))
    assert result is False
    entry = _latest_audit_entry("TEST_EMAIL_EVENT")
    assert entry is not None
    assert entry.meta["to"] == "nobody@test.com"


def test_email_send_via_sendgrid_when_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "sendgrid_enabled", True)
    monkeypatch.setattr(settings, "sendgrid_api_key", "SG.test-key")
    monkeypatch.setattr(settings, "sendgrid_from_email", "noreply@test.com")

    class _FakeResponse:
        status_code = 202
        text = ""

    class _FakeAsyncClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None, headers=None):
            assert url == "https://api.sendgrid.com/v3/mail/send"
            assert headers["Authorization"] == "Bearer SG.test-key"
            assert json["personalizations"][0]["to"][0]["email"] == "someone@test.com"
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    result = asyncio.run(EmailService.send(
        "someone@test.com", "Hello", "<p>hi</p>", event_code="TEST_EMAIL_SENT_EVENT",
    ))
    assert result is True
    assert _latest_audit_entry("TEST_EMAIL_SENT_EVENT") is not None


def test_email_send_failure_is_logged_not_raised(client, monkeypatch):
    monkeypatch.setattr(settings, "sendgrid_enabled", True)
    monkeypatch.setattr(settings, "sendgrid_api_key", "SG.test-key")
    monkeypatch.setattr(settings, "sendgrid_from_email", "noreply@test.com")

    class _FakeAsyncClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    result = asyncio.run(EmailService.send(
        "someone@test.com", "Hello", "<p>hi</p>", event_code="TEST_EMAIL_ERROR_EVENT",
    ))
    assert result is False  # never raises
    assert _latest_audit_entry("EMAIL_SEND_ERROR") is not None


# ── Wiring: order confirmation, status change, low stock ────────────────

def test_order_confirmation_email_attempted_on_checkout(client):
    admin_token = _admin_token(client, email="emailadmin2@test.com")
    customer_token = _register_customer(client, email="emailcustomer2@test.com")
    product_id = _create_product(client, admin_token, sku="email-item-2")
    order = _place_order(client, customer_token, product_id)

    entry = _latest_audit_entry("ORDER_CONFIRMATION_EMAIL_SENT")
    assert entry is not None
    assert entry.meta["order_id"] == order["id"]
    # Phase 5 item 1: the confirmation email carries the same PDF invoice GET
    # /orders/{id}/invoice serves on demand.
    assert entry.meta["attachments"] == [f"invoice-{order['id']}.pdf"]


def test_order_confirmation_email_attachment_is_a_real_pdf_via_sendgrid(client, monkeypatch):
    """With SendGrid configured, the invoice must actually reach the API payload as a base64
    PDF attachment, not just a filename in the dev-log fallback path."""
    monkeypatch.setattr(settings, "sendgrid_enabled", True)
    monkeypatch.setattr(settings, "sendgrid_api_key", "SG.test-key")
    monkeypatch.setattr(settings, "sendgrid_from_email", "noreply@test.com")

    captured = {}

    class _FakeResponse:
        status_code = 202
        text = ""

    class _FakeAsyncClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None, headers=None):
            if json.get("attachments"):
                captured.update(json)
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    admin_token = _admin_token(client, email="emailadmin9@test.com")
    customer_token = _register_customer(client, email="emailcustomer9@test.com")
    product_id = _create_product(client, admin_token, sku="email-item-9")
    order = _place_order(client, customer_token, product_id)

    assert captured, "expected the confirmation email's POST to SendGrid to include an attachment"
    attachment = captured["attachments"][0]
    assert attachment["filename"] == f"invoice-{order['id']}.pdf"
    assert attachment["type"] == "application/pdf"

    import base64
    pdf_bytes = base64.b64decode(attachment["content"])
    assert pdf_bytes.startswith(b"%PDF")


def test_order_status_change_email_attempted(client):
    admin_token = _admin_token(client, email="emailadmin3@test.com")
    customer_token = _register_customer(client, email="emailcustomer3@test.com")
    product_id = _create_product(client, admin_token, sku="email-item-3")
    order = _place_order(client, customer_token, product_id)

    resp = client.patch(
        f"/orders/{order['id']}/status",
        json={"status": "confirmed", "note": "Confirmed"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text

    entry = _latest_audit_entry("ORDER_STATUS_EMAIL_SENT")
    assert entry is not None
    assert entry.meta["order_id"] == order["id"]
    assert entry.meta["status"] == "confirmed"


def test_packed_status_does_not_trigger_customer_email(client):
    """"packed" is an internal warehouse step, not customer-meaningful — see
    services/order_user.py::_CUSTOMER_NOTIFIED_STATUSES."""
    admin_token = _admin_token(client, email="emailadmin4@test.com")
    customer_token = _register_customer(client, email="emailcustomer4@test.com")
    product_id = _create_product(client, admin_token, sku="email-item-4")
    order = _place_order(client, customer_token, product_id)

    client.patch(
        f"/orders/{order['id']}/status", json={"status": "confirmed"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    before = _count_audit_entries("ORDER_STATUS_EMAIL_SENT")

    resp = client.patch(
        f"/orders/{order['id']}/status", json={"status": "packed"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text

    after = _count_audit_entries("ORDER_STATUS_EMAIL_SENT")
    assert after == before  # no new email attempt for "packed"


def test_low_stock_alert_fires_once_at_threshold_crossing(client):
    admin_token = _admin_token(client, email="emailadmin5@test.com")
    customer_token = _register_customer(client, email="emailcustomer5@test.com")
    # default threshold is 10 — start at 11 so a single order of qty 2 crosses it (11 -> 9).
    product_id = _create_product(client, admin_token, sku="email-item-5", stock=11)

    _place_order(client, customer_token, product_id, quantity=2)
    after_first = _count_audit_entries("LOW_STOCK_ALERT_SENT")
    assert after_first >= 1

    # A second order that keeps stock below the threshold must NOT re-fire the alert.
    _place_order(client, customer_token, product_id, quantity=1)
    after_second = _count_audit_entries("LOW_STOCK_ALERT_SENT")
    assert after_second == after_first
