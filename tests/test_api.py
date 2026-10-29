from datetime import datetime, timezone

from fastapi.testclient import TestClient

from riskmesh.api import app

client = TestClient(app)


def payload(identifier="txn-1", tenant="tenantA"):
    return {
        "transaction_id": identifier,
        "timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
        "tenant_id": tenant,
        "sender_account": "A",
        "receiver_account": "B",
        "amount": 100,
        "currency": "USD",
        "device_id": "device-1",
        "source_ip": "192.0.2.1",
        "country": "US",
        "channel": "web",
    }


def test_health_and_dashboard():
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200


def test_api_key_and_tenant_persistence(tmp_path, monkeypatch):
    monkeypatch.setenv("RISK_MESH_DB_PATH", str(tmp_path / "risk.db"))
    monkeypatch.setenv("RISK_MESH_API_KEY", "synthetic-test-key-at-least-24-chars")
    headers = {"X-API-Key": "synthetic-test-key-at-least-24-chars"}
    assert client.post("/api/v1/score", json=payload()).status_code == 401
    response = client.post("/api/v1/score", headers=headers, json=payload())
    assert response.status_code == 200, response.text
    decisions = client.get(
        "/api/v1/decisions",
        headers={**headers, "X-Tenant-ID": "tenantA"},
    )
    assert len(decisions.json()["decisions"]) == 1
    other = client.get(
        "/api/v1/decisions",
        headers={**headers, "X-Tenant-ID": "tenantB"},
    )
    assert other.json()["decisions"] == []
