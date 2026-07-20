"""
Phase 1 (auth hardening master prompt, 2026-07-20):

1a. Refresh tokens must not authenticate as access tokens (middleware/auth_middleware.py).
1b. Banning/deactivating/locking a user must end their session immediately, not just block
    future logins — both on the next authenticated request and on /auth/refresh.
1c. Refresh tokens are revoked on logout and on rotation-reuse (replay of an already-rotated
    refresh token kills every session for that account, not just the replayed one).
1d. Admin lockout is time-based (auto-clears), and /admin/auth/login is rate limited per-IP
    independent of the per-account failed-attempt counter.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from config import settings
from services.admin_auth import AdminAuthService
from utils.helpers import create_access_token, create_refresh_token
from utils.limiter import limiter


def _admin_token(client, email, password, role="admin"):
    asyncio.run(AdminAuthService.create_admin_user(name="Admin", email=email, password=password, role=role))
    resp = client.post("/admin/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _register_customer(client, email, password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "Auth Hardening Customer", "email": email, "password": password, "phone": "03001234567",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── 1a ────────────────────────────────────────────────────────────────────────

def test_refresh_token_rejected_on_access_only_endpoint(client):
    body = _register_customer(client, "rt-as-access@test.com")
    user_id = body["user"]["id"]

    # Mint a real refresh token for this user directly (bypassing the register flow's cookie),
    # and try to use it as a bearer access token.
    refresh_token = create_refresh_token(user_id, "customer")
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {refresh_token}"})
    assert resp.status_code == 401


def test_registered_refresh_cookie_itself_is_rejected_as_access_token(client):
    body = _register_customer(client, "rt-cookie-as-access@test.com")
    refresh_cookie = client.cookies.get("refresh_token")
    assert refresh_cookie

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {refresh_cookie}"})
    assert resp.status_code == 401


# ── 1b ──────────────────────────────────────────────────────────────────────────

def test_banning_user_ends_session_immediately(client):
    body = _register_customer(client, "bantarget@test.com")
    access_token = body["access_token"]
    csrf = client.cookies.get("csrf_token")
    user_id = body["user"]["id"]

    admin_token = _admin_token(client, "banadmin@test.com", "AdminPass123", "super_admin")
    ban_resp = client.post(
        f"/admin/users/{user_id}/ban",
        params={"reason": "hardening test"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert ban_resp.status_code == 200, ban_resp.text

    # The existing (not-yet-expired) access token must stop working immediately.
    me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_resp.status_code == 403

    # And refresh must not be able to mint a new one either.
    refresh_resp = client.post("/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert refresh_resp.status_code == 401


def test_deactivating_rider_ends_session_immediately(client):
    admin_token = _admin_token(client, "riderdeactadmin@test.com", "AdminPass123")
    create_resp = client.post(
        "/admin/riders",
        json={"name": "Deact Rider", "email": "deactrider@test.com", "password": "RiderPass123", "phone": "03008888888"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_resp.status_code == 200, create_resp.text
    rider_id = create_resp.json()["data"]["id"]

    login_resp = client.post("/auth/login", json={"email": "deactrider@test.com", "password": "RiderPass123"})
    assert login_resp.status_code == 200, login_resp.text
    rider_token = login_resp.json()["access_token"]
    csrf = client.cookies.get("csrf_token")

    deact_resp = client.patch(
        f"/admin/riders/{rider_id}/deactivate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert deact_resp.status_code == 200, deact_resp.text

    profile_resp = client.get("/rider/profile", headers={"Authorization": f"Bearer {rider_token}"})
    assert profile_resp.status_code == 403

    refresh_resp = client.post("/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert refresh_resp.status_code == 401


# ── 1c ──────────────────────────────────────────────────────────────────────────

def test_logout_revokes_refresh_token(client):
    body = _register_customer(client, "logout-revoke@test.com")
    access_token = body["access_token"]
    csrf = client.cookies.get("csrf_token")
    refresh_token = client.cookies.get("refresh_token")
    assert refresh_token

    logout_resp = client.post("/auth/logout", headers={"Authorization": f"Bearer {access_token}"})
    assert logout_resp.status_code == 200, logout_resp.text

    # /auth/logout's Set-Cookie clears the cookie in the jar -- re-attach the exact pre-logout
    # refresh_token value to prove the *token itself* (not just the cookie jar) is now dead.
    client.cookies.set("refresh_token", refresh_token)
    client.cookies.set("csrf_token", csrf)
    refresh_resp = client.post("/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert refresh_resp.status_code == 401


def test_refresh_token_replay_after_rotation_kills_all_sessions(client):
    body = _register_customer(client, "reuse-detect@test.com")
    csrf0 = client.cookies.get("csrf_token")
    r0 = client.cookies.get("refresh_token")
    assert r0 and csrf0

    resp1 = client.post("/auth/refresh", headers={"X-CSRF-Token": csrf0})
    assert resp1.status_code == 200, resp1.text
    csrf1 = client.cookies.get("csrf_token")
    r1 = client.cookies.get("refresh_token")
    assert r1 and r1 != r0

    resp2 = client.post("/auth/refresh", headers={"X-CSRF-Token": csrf1})
    assert resp2.status_code == 200, resp2.text
    csrf2 = client.cookies.get("csrf_token")
    r2 = client.cookies.get("refresh_token")
    assert r2 and r2 != r1

    # Replay the very first (already-rotated-out) refresh token -- this is the leak scenario.
    client.cookies.set("refresh_token", r0)
    client.cookies.set("csrf_token", csrf0)
    replay_resp = client.post("/auth/refresh", headers={"X-CSRF-Token": csrf0})
    assert replay_resp.status_code == 401

    # The legitimate, never-yet-used r2 must now be rejected too: reuse detection revokes every
    # session for the account, not just the one that got replayed.
    client.cookies.set("refresh_token", r2)
    client.cookies.set("csrf_token", csrf2)
    resp3 = client.post("/auth/refresh", headers={"X-CSRF-Token": csrf2})
    assert resp3.status_code == 401


# ── 1d ──────────────────────────────────────────────────────────────────────────

def test_admin_lockout_is_time_based_and_auto_clears(client):
    asyncio.run(AdminAuthService.create_admin_user(
        name="Lockout Admin", email="lockoutadmin@test.com", password="AdminPass123", role="admin"
    ))

    resp = None
    for _ in range(5):
        resp = client.post("/admin/auth/login", json={"email": "lockoutadmin@test.com", "password": "WrongPass1"})
    assert resp.status_code == 423, resp.text

    # Correct password still rejected while locked. Reset the per-IP limiter first: this check is
    # about account lockout, not rate limiting, and the 5 failed attempts above already used up
    # this test's slowapi quota for this endpoint.
    limiter.reset()
    still_locked = client.post("/admin/auth/login", json={"email": "lockoutadmin@test.com", "password": "AdminPass123"})
    assert still_locked.status_code == 423

    # Simulate the lockout window having elapsed. Also resets the per-IP rate limiter: by the
    # time a 15-minute lockout window has passed, any 1-minute rate-limit window has long since
    # reset too, so this reflects real elapsed time rather than working around the test.
    async def _backdate_lock():
        from database import AsyncSessionLocal
        from db.admin import AdminUser
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(AdminUser).where(AdminUser.email == "lockoutadmin@test.com"))
            admin = result.scalar_one()
            admin.last_locked_at = datetime.now(timezone.utc) - timedelta(minutes=settings.admin_lockout_minutes + 1)
            await db.commit()

    asyncio.run(_backdate_lock())
    limiter.reset()

    resp = client.post("/admin/auth/login", json={"email": "lockoutadmin@test.com", "password": "AdminPass123"})
    assert resp.status_code == 200, resp.text


def test_admin_login_rate_limited_per_ip_independent_of_account_lockout(client):
    # Six different (nonexistent) admin emails from the same IP -- none can have tripped the
    # per-account counter (each is only tried once), so a block must be the per-IP slowapi limit.
    last_status = None
    for i in range(6):
        resp = client.post("/admin/auth/login", json={"email": f"noexist-{i}@test.com", "password": "whatever"})
        last_status = resp.status_code
    assert last_status == 429
