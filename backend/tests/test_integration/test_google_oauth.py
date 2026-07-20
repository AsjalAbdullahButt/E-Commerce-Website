"""
Phase 2 (Google Sign-In master prompt, 2026-07-20): POST /auth/google, GET /auth/providers,
services/google_auth.py::verify_id_token.

Two layers of test:
  - verify_id_token itself, against a real self-signed RSA keypair standing in for Google's own
    signing key (services.google_auth._fetch_jwks is monkeypatched to return our test JWKS
    instead of a real network call) -- this exercises the actual signature/issuer/audience/
    email_verified checks, not a mock of the whole function.
  - The /auth/google route, which patches verify_id_token directly (per the master prompt) to
    return canned claims, to test the account linking/creation/ban logic in isolation from
    token verification.
"""
import asyncio
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk, jwt

import services.google_auth as google_auth_module
from config import settings
from services.admin_auth import AdminAuthService
from services.google_auth import verify_id_token

TEST_KID = "test-key-1"
TEST_CLIENT_ID = "test-client-id.apps.googleusercontent.com"


def _generate_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    public_jwk = jwk.construct(public_pem, algorithm="RS256").to_dict()
    public_jwk["kid"] = TEST_KID
    public_jwk["use"] = "sig"
    return private_pem, {"keys": [public_jwk]}


_PRIVATE_PEM, _TEST_JWKS = _generate_keypair()


def _make_id_token(**overrides):
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": TEST_CLIENT_ID,
        "sub": "google-sub-123",
        "email": "googleuser@test.com",
        "email_verified": True,
        "name": "Google User",
        "picture": "https://example.com/avatar.png",
        "iat": now,
        "exp": now + 3600,
    }
    claims.update(overrides)
    return jwt.encode(claims, _PRIVATE_PEM, algorithm="RS256", headers={"kid": TEST_KID})


@pytest.fixture(autouse=True)
def _patch_jwks_fetch(monkeypatch):
    """Every test in this file stands in Google's real JWKS endpoint with our own self-signed
    keypair, so verify_id_token's real crypto/issuer/audience checks run against known-good/bad
    tokens without any network call."""
    async def _fake_fetch_jwks():
        return _TEST_JWKS

    monkeypatch.setattr(google_auth_module, "_fetch_jwks", _fake_fetch_jwks)
    monkeypatch.setattr(settings, "google_client_id", TEST_CLIENT_ID)


def _admin_token(client, email="googleoauthadmin@test.com", password="AdminPass123", role="super_admin"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role=role))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


# ── services/google_auth.py::verify_id_token ────────────────────────────────────

def test_verify_id_token_accepts_valid_token(client):
    token = _make_id_token()
    claims = asyncio.run(verify_id_token(token))
    assert claims["email"] == "googleuser@test.com"
    assert claims["sub"] == "google-sub-123"


def test_verify_id_token_rejects_wrong_audience(client):
    token = _make_id_token(aud="someone-elses-client-id")
    with pytest.raises(Exception) as exc_info:
        asyncio.run(verify_id_token(token))
    assert getattr(exc_info.value, "status_code", None) == 401


def test_verify_id_token_rejects_unverified_email(client):
    token = _make_id_token(email_verified=False)
    with pytest.raises(Exception) as exc_info:
        asyncio.run(verify_id_token(token))
    assert getattr(exc_info.value, "status_code", None) == 401


def test_verify_id_token_rejects_wrong_issuer(client):
    token = _make_id_token(iss="https://evil.example.com")
    with pytest.raises(Exception) as exc_info:
        asyncio.run(verify_id_token(token))
    assert getattr(exc_info.value, "status_code", None) == 401


def test_verify_id_token_rejects_expired_token(client):
    now = int(time.time())
    token = _make_id_token(iat=now - 7200, exp=now - 3600)
    with pytest.raises(Exception) as exc_info:
        asyncio.run(verify_id_token(token))
    assert getattr(exc_info.value, "status_code", None) == 401


def test_verify_id_token_rejects_bad_signature(client):
    # Signed with an unrelated keypair -- our test JWKS won't have a matching kid at all.
    other_private_pem, _ = _generate_keypair()
    now = int(time.time())
    bad_token = jwt.encode(
        {"iss": "https://accounts.google.com", "aud": TEST_CLIENT_ID, "sub": "x",
         "email": "x@test.com", "email_verified": True, "iat": now, "exp": now + 3600},
        other_private_pem, algorithm="RS256", headers={"kid": "some-other-kid"},
    )
    with pytest.raises(Exception) as exc_info:
        asyncio.run(verify_id_token(bad_token))
    assert getattr(exc_info.value, "status_code", None) == 401


# ── GET /auth/providers ──────────────────────────────────────────────────────────

def test_providers_endpoint_hides_client_id_when_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "google_oauth_enabled", False)
    resp = client.get("/auth/providers")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["google_oauth_enabled"] is False
    assert body["google_client_id"] is None


def test_providers_endpoint_exposes_client_id_when_enabled(client, monkeypatch):
    monkeypatch.setattr(settings, "google_oauth_enabled", True)
    resp = client.get("/auth/providers")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["google_oauth_enabled"] is True
    assert body["google_client_id"] == TEST_CLIENT_ID


# ── POST /auth/google ─────────────────────────────────────────────────────────────

def test_google_login_disabled_returns_404(client, monkeypatch):
    monkeypatch.setattr(settings, "google_oauth_enabled", False)
    resp = client.post("/auth/google", json={"id_token": "irrelevant"})
    assert resp.status_code == 404


def test_google_login_creates_new_user_matching_login_response_shape(client, monkeypatch):
    monkeypatch.setattr(settings, "google_oauth_enabled", True)
    token = _make_id_token(sub="new-google-user-sub", email="newgoogleuser@test.com")

    resp = client.post("/auth/google", json={"id_token": token})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert set(body.keys()) == {"access_token", "token_type", "user"}
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "newgoogleuser@test.com"
    assert body["user"]["role"] == "customer"
    assert client.cookies.get("refresh_token")
    assert client.cookies.get("csrf_token")

    # A second Google login with the same sub must reuse the same account, not create another.
    resp2 = client.post("/auth/google", json={"id_token": token})
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["user"]["id"] == body["user"]["id"]


def test_google_login_links_existing_local_account_by_email(client, monkeypatch):
    monkeypatch.setattr(settings, "google_oauth_enabled", True)
    register_resp = client.post("/auth/register", json={
        "name": "Local First", "email": "linkme@test.com", "password": "Shopper123", "phone": "03001234567",
    })
    assert register_resp.status_code == 200, register_resp.text
    local_user_id = register_resp.json()["user"]["id"]

    token = _make_id_token(sub="link-google-sub", email="linkme@test.com")
    resp = client.post("/auth/google", json={"id_token": token})
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["id"] == local_user_id

    async def _fetch_user():
        from database import AsyncSessionLocal
        from db.user import User
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == "linkme@test.com"))
            return result.scalar_one()

    linked_user = asyncio.run(_fetch_user())
    assert linked_user.google_sub == "link-google-sub"
    assert linked_user.auth_provider == "local"  # still has a real password -- stays "local"


def test_google_login_rejects_banned_user(client, monkeypatch):
    monkeypatch.setattr(settings, "google_oauth_enabled", True)
    token = _make_id_token(sub="banned-google-sub", email="googlebanned@test.com")
    resp = client.post("/auth/google", json={"id_token": token})
    assert resp.status_code == 200, resp.text
    user_id = resp.json()["user"]["id"]

    admin_token = _admin_token(client)
    ban_resp = client.post(
        f"/admin/users/{user_id}/ban", params={"reason": "test"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert ban_resp.status_code == 200, ban_resp.text

    resp2 = client.post("/auth/google", json={"id_token": token})
    assert resp2.status_code == 403


def test_google_login_response_shape_matches_password_login(client, monkeypatch):
    monkeypatch.setattr(settings, "google_oauth_enabled", True)

    password_resp = client.post("/auth/register", json={
        "name": "Shape Compare", "email": "shapecompare@test.com", "password": "Shopper123", "phone": "03001234567",
    })
    password_body = password_resp.json()

    token = _make_id_token(sub="shape-google-sub", email="shapegoogle@test.com")
    google_resp = client.post("/auth/google", json={"id_token": token})
    google_body = google_resp.json()

    assert set(google_body.keys()) == set(password_body.keys())
    assert set(google_body["user"].keys()) == set(password_body["user"].keys())


# ── change-password / reset-password guards for provider-only accounts ───────────

def test_change_password_rejected_for_google_only_account(client, monkeypatch):
    monkeypatch.setattr(settings, "google_oauth_enabled", True)
    token = _make_id_token(sub="nopass-google-sub", email="nopassgoogle@test.com")
    login_resp = client.post("/auth/google", json={"id_token": token})
    access_token = login_resp.json()["access_token"]

    resp = client.post(
        "/auth/change-password",
        json={"old_password": "whatever", "new_password": "NewPass123"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 400
    assert "Google" in resp.json()["detail"]
