from riskmesh.attestation import sign_decision, verify_decision


def test_signed_decision_detects_tampering(monkeypatch):
    monkeypatch.setenv("RISK_MESH_SIGNING_KEY", "demo-signing-key-with-more-than-32-characters")
    envelope = sign_decision({"tenant": "alpha", "score": 70})
    assert verify_decision(envelope)
    envelope["document"]["payload"]["score"] = 1
    assert not verify_decision(envelope)


def test_advanced_investigation_api(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from riskmesh.api import app

    monkeypatch.setenv("RISK_MESH_DB_PATH", str(tmp_path / "advanced.db"))
    monkeypatch.setenv("RISK_MESH_API_KEY", "demo-api-key-with-more-than-24-characters")
    monkeypatch.setenv("RISK_MESH_SIGNING_KEY", "demo-signing-key-with-more-than-32-characters")
    client = TestClient(app)
    headers = {"X-API-Key": "demo-api-key-with-more-than-24-characters"}
    payload = {
        "transaction_id": "advanced-1",
        "timestamp": "2026-10-29T12:00:00Z",
        "tenant_id": "alpha",
        "sender_account": "A",
        "receiver_account": "B",
        "amount": 500,
        "currency": "USD",
        "device_id": "d1",
        "source_ip": "192.0.2.1",
        "country": "US",
        "channel": "api",
    }
    response = client.post("/api/v1/advanced/investigate", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    envelope = response.json()
    assert envelope["document"]["payload"]["model_version"] == "temporal-graph-v1"
    verification = client.post(
        "/api/v1/advanced/verify", json={"envelope": envelope}, headers=headers
    )
    assert verification.json() == {"valid": True}
