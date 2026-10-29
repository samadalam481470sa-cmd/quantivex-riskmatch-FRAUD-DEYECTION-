from fastapi.testclient import TestClient

from riskmesh.api import app
from riskmesh.demo import CASES, analyze

client = TestClient(app)


def test_read_only_synthetic_cases_exercise_real_engine():
    results = {case["id"]: analyze(case["id"]) for case in CASES}
    assert results["legitimate"]["decision"] == "allow"
    assert results["amount-spike"]["risk_score"] > results["legitimate"]["risk_score"]
    assert results["circular-ring"]["decision"] == "block"
    assert any(
        finding["code"] == "TEMPORAL_CIRCULAR_FLOW"
        for finding in results["circular-ring"]["temporal_graph_findings"]
    )
    assert any(
        finding["code"] == "AGGREGATION_LAYERING"
        for finding in results["layering"]["temporal_graph_findings"]
    )
    assert all(item["data_source"] == "fixed-synthetic-only" for item in results.values())


def test_demo_http_routes_work_without_credentials(monkeypatch):
    monkeypatch.delenv("RISK_MESH_ENV", raising=False)
    listing = client.get("/api/v1/demo/cases")
    assert listing.status_code == 200
    assert len(listing.json()["cases"]) == 4
    assert client.get("/assets/dashboard.css").status_code == 200
    assert client.get("/assets/dashboard.js").status_code == 200
    assert "Run investigation" in client.get("/").text
    result = client.get("/api/v1/demo/investigate/circular-ring")
    assert result.status_code == 200
    assert result.json()["decision"] == "block"
    assert client.get("/api/v1/demo/investigate/does-not-exist").status_code == 404


def test_public_showcase_blocks_financial_transaction_apis(monkeypatch):
    monkeypatch.setenv("RISK_MESH_PUBLIC_DEMO", "true")
    monkeypatch.setenv("RISK_MESH_API_KEY", "example-credential-with-minimum-length")
    transaction = {
        "transaction_id": "demo-test", "timestamp": "2026-01-01T12:00:00Z",
        "tenant_id": "public-synthetic-demo", "sender_account": "a",
        "receiver_account": "b", "amount": 5, "currency": "USD",
        "device_id": "d", "source_ip": "192.0.2.1",
        "country": "US", "channel": "api",
    }
    assert client.post(
        "/api/v1/score", headers={"X-API-Key": "example-credential-with-minimum-length"},
        json=transaction,
    ).status_code == 404


def test_demo_is_disabled_in_restricted_mode(monkeypatch):
    monkeypatch.setenv("RISK_MESH_ENV", "production")
    assert client.get("/api/v1/demo/cases").status_code == 404
    assert client.get("/api/v1/demo/investigate/legitimate").status_code == 404
