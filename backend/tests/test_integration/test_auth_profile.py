"""
Fills gaps in routes/auth.py coverage: POST /auth/logout, PUT /auth/profile, PATCH /auth/me, and
POST /auth/change-password had no dedicated tests before this file (register/login/refresh/
forgot-password/reset-password are covered elsewhere). Also covers GET /products/categories
(routes/products.py), a one-off gap not worth its own file.
"""
def _register_customer(client, email="authprofile@test.com", password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "Auth Profile Customer", "email": email, "password": password, "phone": "03001234567",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_logout_clears_refresh_cookie(client):
    token = _register_customer(client)
    assert client.cookies.get("refresh_token")

    resp = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    assert client.cookies.get("refresh_token") is None


def test_logout_requires_auth(client):
    resp = client.post("/auth/logout")
    assert resp.status_code == 401


def test_put_profile_updates_name_phone_address(client):
    token = _register_customer(client, email="authprofile2@test.com")
    resp = client.put(
        "/auth/profile",
        json={"name": "Updated Name", "phone": "03009999999", "address": "42 New Street"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    user = resp.json()["user"]
    assert user["name"] == "Updated Name"
    assert user["phone"] == "03009999999"
    assert user["address"] == "42 New Street"


def test_put_profile_with_no_fields_rejected(client):
    token = _register_customer(client, email="authprofile3@test.com")
    resp = client.put("/auth/profile", json={}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400


def test_patch_me_updates_profile(client):
    token = _register_customer(client, email="authprofile4@test.com")
    resp = client.patch(
        "/auth/me",
        json={"name": "Patched Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text

    me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.json()["name"] == "Patched Name"


def test_change_password_success_and_relogin(client):
    email = "authprofile5@test.com"
    token = _register_customer(client, email=email, password="OldPass123")

    resp = client.post(
        "/auth/change-password",
        json={"old_password": "OldPass123", "new_password": "NewPass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text

    old_login = client.post("/auth/login", json={"email": email, "password": "OldPass123"})
    assert old_login.status_code == 401

    new_login = client.post("/auth/login", json={"email": email, "password": "NewPass456"})
    assert new_login.status_code == 200


def test_change_password_wrong_old_password_rejected(client):
    token = _register_customer(client, email="authprofile6@test.com", password="OldPass123")
    resp = client.post(
        "/auth/change-password",
        json={"old_password": "WrongPass123", "new_password": "NewPass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


def test_change_password_weak_new_password_rejected(client):
    token = _register_customer(client, email="authprofile7@test.com", password="OldPass123")
    resp = client.post(
        "/auth/change-password",
        json={"old_password": "OldPass123", "new_password": "weak"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_products_categories_reachable(client):
    resp = client.get("/products/categories")
    assert resp.status_code == 200
    assert isinstance(resp.json()["categories"], list)
