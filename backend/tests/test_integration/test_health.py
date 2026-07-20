"""GET /health (main.py) — a real DB-connectivity probe for a load balancer/orchestrator, unlike
GET /` which is a static "ok" regardless of database state.
"""


def test_health_reports_ok_when_db_reachable(client):
    resp = client.get("/health")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"


def test_root_still_returns_static_ok(client):
    resp = client.get("/")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ok"


def test_health_reports_503_when_db_unreachable(client, monkeypatch):
    class _BrokenEngine:
        def connect(self):
            raise ConnectionRefusedError("simulated DB outage")

    monkeypatch.setattr("main.engine", _BrokenEngine())
    resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json()["status"] == "error"
