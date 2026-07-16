"""
Regression test for the customer forgot-password flow (NOTES_schema_audit.md §7 / task 8).
No SMTP/email provider is configured, so routes/auth.py logs the reset link via log_to_db
instead of emailing it (a documented dev stand-in) — this test reads it back from
audit_logs_col, the same way a real email would carry the token, to drive the flow end-to-end.
"""
from urllib.parse import urlparse, parse_qs

import database


def _register_customer(client, email="forgot@test.com", password="OldPass123"):
    resp = client.post("/auth/register", json={
        "name": "Forgetful", "email": email, "password": password, "phone": "03001234567",
    })
    assert resp.status_code == 200, resp.text


def _latest_reset_token(email):
    import asyncio

    async def _fetch():
        doc = await database.audit_logs_col.find_one(
            {"level": "PASSWORD_RESET_REQUESTED"}, sort=[("timestamp", -1)]
        )
        return doc

    doc = asyncio.run(_fetch())
    assert doc is not None, "no PASSWORD_RESET_REQUESTED audit entry was logged"
    link = doc["meta"]["reset_link"]
    token = parse_qs(urlparse(link).query)["token"][0]
    return token


def test_forgot_password_generates_working_single_use_token(client):
    _register_customer(client)

    forgot_resp = client.post("/auth/forgot-password", json={"email": "forgot@test.com"})
    assert forgot_resp.status_code == 200
    token = _latest_reset_token("forgot@test.com")

    reset_resp = client.post("/auth/reset-password", json={"token": token, "new_password": "NewPass456"})
    assert reset_resp.status_code == 200, reset_resp.text

    # Old password no longer works, new one does.
    old_login = client.post("/auth/login", json={"email": "forgot@test.com", "password": "OldPass123"})
    assert old_login.status_code == 401

    new_login = client.post("/auth/login", json={"email": "forgot@test.com", "password": "NewPass456"})
    assert new_login.status_code == 200

    # Token is single-use — replaying it fails even with a fresh password.
    replay_resp = client.post("/auth/reset-password", json={"token": token, "new_password": "AnotherPass789"})
    assert replay_resp.status_code == 400


def test_forgot_password_does_not_leak_whether_email_exists(client):
    known = client.post("/auth/forgot-password", json={"email": "nonexistent@test.com"})
    assert known.status_code == 200
    assert "sent" in known.json()["message"].lower()
