import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from riskmesh.api import app
from riskmesh.identity import verify_token
from riskmesh.telemetry import metrics_response, record


def test_reject_missing_oidc_configuration(monkeypatch):
    monkeypatch.delenv("RISK_MESH_OIDC_ISSUER", raising=False)
    with pytest.raises(HTTPException) as exc:
        verify_token("fake")
    assert exc.value.status_code == 503


def test_metrics_do_not_include_private_account_path():
    record("/api/v1/exposure/secret-account-number", 404)
    assert "secret-account-number" not in metrics_response().body.decode()


def test_security_headers_on_demo():
    response = TestClient(app).get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
