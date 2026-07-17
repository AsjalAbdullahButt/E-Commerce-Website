"""Tests for POST /payments/{order_id}/initiate, POST /payments/webhook/{gateway}, and
GET /payments/{order_id}/status (routes/payments.py) — plus the Idempotency-Key handling and
payment_status defaults added to POST /orders (routes/orders.py).

Every gateway is disabled by default (no credentials in the test environment, mirroring
.env.example) — most tests exercise that "runs locally without real credentials" contract
directly. The end-to-end flow test monkeypatches JazzCash's settings on so the full
initiate -> signed callback -> order-confirmed path can be exercised without real credentials,
since JazzCash's HMAC signing needs no external SDK/network call (unlike Stripe).
"""
import asyncio
import hashlib
import hmac

from config import settings
from services.admin_auth import AdminAuthService


def _admin_token(client, email="paymentsadmin@test.com", password="AdminPass123"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role="admin"))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


def _register_customer(client, email="paymentscustomer@test.com", password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "Payments Customer", "email": email, "password": password, "phone": "03001234567",
    })
    return resp.json()["access_token"]


def _create_product(client, admin_token, sku="payments-item"):
    resp = client.post(
        "/admin/products",
        json={
            "name": "Payments Item", "description": "test", "category": "accessories",
            "price": 1000, "discount_percentage": 0, "tags": [], "images": [],
            "variants": [{"size": "One Size", "color": "Black", "sku": sku, "stock": 15}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return resp.json()["data"]["product_id"]


def _place_order(client, customer_token, product_id, payment_method="cod", extra_headers=None):
    headers = {"Authorization": f"Bearer {customer_token}"}
    if extra_headers:
        headers.update(extra_headers)
    resp = client.post(
        "/orders",
        json={
            "items": [{
                "product_id": product_id, "name": "x", "price": 1000,
                "quantity": 1, "size": "One Size", "color": "Black", "image": "",
            }],
            "shipping_address": {
                "full_name": "Payments Customer", "phone": "03001234567",
                "address": "1 Test Rd", "city": "Karachi", "postal_code": "75000",
            },
            "payment_method": payment_method,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _jazzcash_secure_hash(fields: dict, salt: str) -> str:
    ordered_values = "&".join(str(fields[k]) for k in sorted(fields) if fields.get(k) not in (None, ""))
    message = f"{salt}&{ordered_values}"
    return hmac.new(salt.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest().upper()


# ── Order idempotency + payment_status defaults ─────────────────────────────

def test_cod_order_has_not_required_payment_status(client):
    admin_token = _admin_token(client)
    customer_token = _register_customer(client)
    product_id = _create_product(client, admin_token)
    order = _place_order(client, customer_token, product_id, payment_method="cod")
    assert order["payment_status"] == "not_required"


def test_online_order_has_unpaid_payment_status(client):
    admin_token = _admin_token(client, email="paymentsadmin2@test.com")
    customer_token = _register_customer(client, email="paymentscustomer2@test.com")
    product_id = _create_product(client, admin_token, sku="payments-item-2")
    order = _place_order(client, customer_token, product_id, payment_method="jazzcash")
    assert order["payment_status"] == "unpaid"


def test_retried_checkout_with_same_idempotency_key_returns_same_order(client):
    admin_token = _admin_token(client, email="paymentsadmin3@test.com")
    customer_token = _register_customer(client, email="paymentscustomer3@test.com")
    product_id = _create_product(client, admin_token, sku="payments-item-3")

    key = {"Idempotency-Key": "test-idem-key-123"}
    order1 = _place_order(client, customer_token, product_id, extra_headers=key)
    order2 = _place_order(client, customer_token, product_id, extra_headers=key)

    assert order1["id"] == order2["id"]

    resp = client.get("/orders", headers={"Authorization": f"Bearer {admin_token}"})
    matches = [o for o in resp.json()["data"] if o["id"] == order1["id"]]
    assert len(matches) == 1  # stock was decremented once, not twice


# ── Payment methods / return redirect ───────────────────────────────────

def test_payment_methods_defaults_to_cod_only(client):
    resp = client.get("/payments/methods")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["cod"] is True
    assert data["stripe"] is False
    assert data["jazzcash"] is False
    assert data["easypaisa"] is False
    assert data["stripe_publishable_key"] is None


def test_payment_return_redirects_to_tracking_page_with_resolved_order(client, monkeypatch):
    monkeypatch.setattr(settings, "jazzcash_enabled", True)
    monkeypatch.setattr(settings, "jazzcash_merchant_id", "TESTMERCHANT")
    monkeypatch.setattr(settings, "jazzcash_password", "testpass")
    monkeypatch.setattr(settings, "jazzcash_integrity_salt", "testsalt123")

    admin_token = _admin_token(client, email="paymentsadmin11@test.com")
    customer_token = _register_customer(client, email="paymentscustomer11@test.com")
    product_id = _create_product(client, admin_token, sku="payments-item-11")
    order = _place_order(client, customer_token, product_id, payment_method="jazzcash")

    initiate_resp = client.post(
        f"/payments/{order['id']}/initiate",
        json={"gateway": "jazzcash"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    payment_id = initiate_resp.json()["payment_id"]

    resp = client.post(
        "/payments/return/jazzcash", data={"pp_TxnRefNo": f"T{payment_id}"}, follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"{settings.frontend_url}/customer/tracking.html?id={order['id']}"


def test_payment_return_with_unresolvable_reference_redirects_without_id(client):
    resp = client.get("/payments/return/jazzcash", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == f"{settings.frontend_url}/customer/tracking.html"


# ── Payment initiate ─────────────────────────────────────────────────────

def test_initiate_payment_requires_matching_order_owner(client):
    admin_token = _admin_token(client, email="paymentsadmin4@test.com")
    owner_token = _register_customer(client, email="paymentsowner@test.com")
    other_token = _register_customer(client, email="paymentsintruder@test.com")
    product_id = _create_product(client, admin_token, sku="payments-item-4")
    order = _place_order(client, owner_token, product_id, payment_method="jazzcash")

    resp = client.post(
        f"/payments/{order['id']}/initiate",
        json={"gateway": "jazzcash"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


def test_initiate_payment_rejects_unknown_gateway(client):
    admin_token = _admin_token(client, email="paymentsadmin5@test.com")
    customer_token = _register_customer(client, email="paymentscustomer5@test.com")
    product_id = _create_product(client, admin_token, sku="payments-item-5")
    order = _place_order(client, customer_token, product_id, payment_method="jazzcash")

    resp = client.post(
        f"/payments/{order['id']}/initiate",
        json={"gateway": "paypal"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 422


def test_initiate_payment_fails_when_gateway_not_configured(client):
    """Every gateway defaults to disabled with no credentials in .env.example / the test
    environment — this is exactly the "runs locally without real credentials" contract."""
    admin_token = _admin_token(client, email="paymentsadmin6@test.com")
    customer_token = _register_customer(client, email="paymentscustomer6@test.com")
    product_id = _create_product(client, admin_token, sku="payments-item-6")
    order = _place_order(client, customer_token, product_id, payment_method="jazzcash")

    resp = client.post(
        f"/payments/{order['id']}/initiate",
        json={"gateway": "jazzcash"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 503


def test_initiate_payment_rejects_invalid_order_id(client):
    customer_token = _register_customer(client, email="paymentscustomer7@test.com")
    resp = client.post(
        "/payments/not-a-real-id/initiate",
        json={"gateway": "jazzcash"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 400


# ── Payment status ───────────────────────────────────────────────────────

def test_payment_status_for_cod_order(client):
    admin_token = _admin_token(client, email="paymentsadmin9@test.com")
    customer_token = _register_customer(client, email="paymentscustomer9@test.com")
    product_id = _create_product(client, admin_token, sku="payments-item-9")
    order = _place_order(client, customer_token, product_id, payment_method="cod")

    resp = client.get(f"/payments/{order['id']}/status", headers={"Authorization": f"Bearer {customer_token}"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["payment_status"] == "not_required"
    assert resp.json()["gateway"] is None


def test_payment_status_denied_for_other_customer(client):
    admin_token = _admin_token(client, email="paymentsadmin10@test.com")
    owner_token = _register_customer(client, email="paymentsowner2@test.com")
    other_token = _register_customer(client, email="paymentsintruder2@test.com")
    product_id = _create_product(client, admin_token, sku="payments-item-10")
    order = _place_order(client, owner_token, product_id, payment_method="cod")

    resp = client.get(f"/payments/{order['id']}/status", headers={"Authorization": f"Bearer {other_token}"})
    assert resp.status_code == 403


# ── Webhook ──────────────────────────────────────────────────────────────

def test_webhook_for_unconfigured_gateway_returns_503(client):
    resp = client.post("/payments/webhook/jazzcash", data={"pp_ResponseCode": "000"})
    assert resp.status_code == 503


def test_webhook_for_unknown_gateway_returns_404(client):
    resp = client.post("/payments/webhook/unknownpay", data={})
    assert resp.status_code == 404


# ── End-to-end JazzCash flow (signature-only, no real network call) ────────

def test_jazzcash_end_to_end_payment_flow(client, monkeypatch):
    monkeypatch.setattr(settings, "jazzcash_enabled", True)
    monkeypatch.setattr(settings, "jazzcash_merchant_id", "TESTMERCHANT")
    monkeypatch.setattr(settings, "jazzcash_password", "testpass")
    monkeypatch.setattr(settings, "jazzcash_integrity_salt", "testsalt123")
    monkeypatch.setattr(settings, "jazzcash_sandbox", True)

    admin_token = _admin_token(client, email="paymentsadmin8@test.com")
    customer_token = _register_customer(client, email="paymentscustomer8@test.com")
    product_id = _create_product(client, admin_token, sku="payments-item-8")
    order = _place_order(client, customer_token, product_id, payment_method="jazzcash")

    # 1. Initiate — signed form fields + redirect, nothing marked paid yet.
    resp = client.post(
        f"/payments/{order['id']}/initiate",
        json={"gateway": "jazzcash"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["gateway"] == "jazzcash"
    assert data["redirect_url"]
    fields = data["form_fields"]
    payment_id = data["payment_id"]
    assert fields["pp_TxnRefNo"] == f"T{payment_id}"

    # 2. A retried initiate (e.g. a double click) reuses the same attempt instead of starting a
    # second one / calling the gateway again.
    resp2 = client.post(
        f"/payments/{order['id']}/initiate",
        json={"gateway": "jazzcash"},
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp2.json()["payment_id"] == payment_id

    # 3. Simulate JazzCash's server-to-server callback with a correctly-signed success payload —
    # the only thing that's ever allowed to mark this paid.
    callback_fields = {
        "pp_TxnRefNo": fields["pp_TxnRefNo"],
        "pp_ResponseCode": "000",
        "pp_ResponseMessage": "Transaction Successful",
        "pp_Amount": fields["pp_Amount"],
        "pp_BillReference": order["id"],
        "pp_RetreivalReferenceNo": "123456789012",
    }
    callback_fields["pp_SecureHash"] = _jazzcash_secure_hash(callback_fields, "testsalt123")

    webhook_resp = client.post("/payments/webhook/jazzcash", data=callback_fields)
    assert webhook_resp.status_code == 200, webhook_resp.text
    assert webhook_resp.json()["duplicate"] is False

    # 4. Order + payment status now reflect the confirmed payment — pending auto-advanced to
    # confirmed, the same transition an admin would otherwise make manually.
    status_resp = client.get(
        f"/payments/{order['id']}/status", headers={"Authorization": f"Bearer {customer_token}"}
    )
    assert status_resp.json()["payment_status"] == "paid"

    order_resp = client.get(f"/orders/{order['id']}", headers={"Authorization": f"Bearer {customer_token}"})
    assert order_resp.json()["status"] == "confirmed"
    assert order_resp.json()["payment_status"] == "paid"

    # 5. A redelivered webhook for the same event is a no-op, not a double-processed transition.
    replay_resp = client.post("/payments/webhook/jazzcash", data=callback_fields)
    assert replay_resp.status_code == 200
    assert replay_resp.json()["duplicate"] is True


def test_jazzcash_webhook_rejects_bad_signature(client, monkeypatch):
    monkeypatch.setattr(settings, "jazzcash_enabled", True)
    monkeypatch.setattr(settings, "jazzcash_merchant_id", "TESTMERCHANT")
    monkeypatch.setattr(settings, "jazzcash_password", "testpass")
    monkeypatch.setattr(settings, "jazzcash_integrity_salt", "testsalt123")

    resp = client.post("/payments/webhook/jazzcash", data={
        "pp_TxnRefNo": "Tabc123", "pp_ResponseCode": "000", "pp_SecureHash": "not-a-real-hash",
    })
    assert resp.status_code == 400
