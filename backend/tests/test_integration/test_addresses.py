"""Tests for GET/POST/PUT/DELETE /addresses and POST /addresses/{id}/default
(services/address.py) — the "at most one default" invariant is enforced in the service layer,
not a DB constraint, so it's the main thing worth exercising here.
"""
def _register_customer(client, email="addresscustomer@test.com", password="Shopper123"):
    resp = client.post("/auth/register", json={
        "name": "Address Customer", "email": email, "password": password, "phone": "03001234567",
    })
    return resp.json()["access_token"]


def _address_payload(**overrides):
    payload = {
        "label": "Home", "full_name": "Address Customer", "phone": "03001234567",
        "address": "1 Address Rd", "city": "Karachi", "postal_code": "75000", "is_default": False,
    }
    payload.update(overrides)
    return payload


def test_first_address_becomes_default_even_if_not_requested(client):
    token = _register_customer(client)
    resp = client.post("/addresses", json=_address_payload(is_default=False), headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_default"] is True


def test_second_address_is_not_default_unless_requested(client):
    token = _register_customer(client, email="addresscustomer2@test.com")
    client.post("/addresses", json=_address_payload(), headers={"Authorization": f"Bearer {token}"})
    resp = client.post("/addresses", json=_address_payload(label="Work"), headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["is_default"] is False


def test_creating_new_default_unsets_previous_default(client):
    token = _register_customer(client, email="addresscustomer3@test.com")
    first = client.post("/addresses", json=_address_payload(), headers={"Authorization": f"Bearer {token}"}).json()
    assert first["is_default"] is True

    second = client.post(
        "/addresses", json=_address_payload(label="Work", is_default=True),
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert second["is_default"] is True

    listing = client.get("/addresses", headers={"Authorization": f"Bearer {token}"}).json()
    defaults = [a for a in listing if a["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == second["id"]


def test_list_addresses_orders_default_first(client):
    token = _register_customer(client, email="addresscustomer4@test.com")
    client.post("/addresses", json=_address_payload(label="Home"), headers={"Authorization": f"Bearer {token}"})
    client.post("/addresses", json=_address_payload(label="Work", is_default=True), headers={"Authorization": f"Bearer {token}"})

    listing = client.get("/addresses", headers={"Authorization": f"Bearer {token}"}).json()
    assert listing[0]["is_default"] is True


def test_update_address_fields(client):
    token = _register_customer(client, email="addresscustomer5@test.com")
    addr = client.post("/addresses", json=_address_payload(), headers={"Authorization": f"Bearer {token}"}).json()

    resp = client.put(
        f"/addresses/{addr['id']}", json=_address_payload(city="Lahore", is_default=True),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["city"] == "Lahore"


def test_set_default_explicitly(client):
    token = _register_customer(client, email="addresscustomer6@test.com")
    first = client.post("/addresses", json=_address_payload(label="Home"), headers={"Authorization": f"Bearer {token}"}).json()
    second = client.post("/addresses", json=_address_payload(label="Work"), headers={"Authorization": f"Bearer {token}"}).json()
    assert first["is_default"] is True
    assert second["is_default"] is False

    resp = client.post(f"/addresses/{second['id']}/default", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_default"] is True

    listing = client.get("/addresses", headers={"Authorization": f"Bearer {token}"}).json()
    first_after = next(a for a in listing if a["id"] == first["id"])
    assert first_after["is_default"] is False


def test_unsetting_default_on_update_promotes_another(client):
    """Editing the currently-default address and explicitly clearing is_default must never leave
    zero defaults — services/address.py::update_address promotes another saved address instead."""
    token = _register_customer(client, email="addresscustomer9@test.com")
    first = client.post("/addresses", json=_address_payload(label="Home"), headers={"Authorization": f"Bearer {token}"}).json()
    client.post("/addresses", json=_address_payload(label="Work"), headers={"Authorization": f"Bearer {token}"})
    assert first["is_default"] is True

    client.put(
        f"/addresses/{first['id']}", json=_address_payload(label="Home", is_default=False),
        headers={"Authorization": f"Bearer {token}"},
    )

    listing = client.get("/addresses", headers={"Authorization": f"Bearer {token}"}).json()
    defaults = [a for a in listing if a["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] != first["id"]


def test_unsetting_default_on_sole_address_stays_default(client):
    token = _register_customer(client, email="addresscustomer10@test.com")
    only = client.post("/addresses", json=_address_payload(), headers={"Authorization": f"Bearer {token}"}).json()
    assert only["is_default"] is True

    resp = client.put(
        f"/addresses/{only['id']}", json=_address_payload(is_default=False),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.json()["is_default"] is True  # forced back — a lone address can't be non-default


def test_delete_default_promotes_another(client):
    token = _register_customer(client, email="addresscustomer7@test.com")
    first = client.post("/addresses", json=_address_payload(label="Home"), headers={"Authorization": f"Bearer {token}"}).json()
    client.post("/addresses", json=_address_payload(label="Work"), headers={"Authorization": f"Bearer {token}"})

    resp = client.delete(f"/addresses/{first['id']}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text

    listing = client.get("/addresses", headers={"Authorization": f"Bearer {token}"}).json()
    assert len(listing) == 1
    assert listing[0]["is_default"] is True


def test_delete_last_address_leaves_empty_list(client):
    token = _register_customer(client, email="addresscustomer8@test.com")
    addr = client.post("/addresses", json=_address_payload(), headers={"Authorization": f"Bearer {token}"}).json()
    client.delete(f"/addresses/{addr['id']}", headers={"Authorization": f"Bearer {token}"})

    listing = client.get("/addresses", headers={"Authorization": f"Bearer {token}"}).json()
    assert listing == []


def test_cannot_access_another_customers_address(client):
    owner_token = _register_customer(client, email="addressowner@test.com")
    other_token = _register_customer(client, email="addressintruder@test.com")
    addr = client.post("/addresses", json=_address_payload(), headers={"Authorization": f"Bearer {owner_token}"}).json()

    update_resp = client.put(
        f"/addresses/{addr['id']}", json=_address_payload(city="Nowhere"),
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert update_resp.status_code == 404

    delete_resp = client.delete(f"/addresses/{addr['id']}", headers={"Authorization": f"Bearer {other_token}"})
    assert delete_resp.status_code == 404


def test_addresses_require_authentication(client):
    resp = client.get("/addresses")
    assert resp.status_code in (401, 403)
