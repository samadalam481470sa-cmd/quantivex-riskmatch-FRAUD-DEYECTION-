import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from riskmesh.api import app
from riskmesh.security import tenant_scope, validate_runtime


def test_production_requires_explicit_configuration(monkeypatch):
    monkeypatch.setenv("RISK_MESH_ENV", "production")
    monkeypatch.delenv("RISK_MESH_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        validate_runtime()


def test_production_tenant_isolation(monkeypatch):
    monkeypatch.setenv("RISK_MESH_ENV", "production")
    monkeypatch.setenv("RISK_MESH_TENANT_ID", "authorized")
    assert tenant_scope("authorized") == "authorized"
    with pytest.raises(HTTPException) as error:
        tenant_scope("other")
    assert error.value.status_code == 403


def test_dashboard_disabled_in_production(monkeypatch):
    monkeypatch.setenv("RISK_MESH_ENV", "production")
    monkeypatch.delenv("RISK_MESH_ENABLE_DEMO", raising=False)
    response = TestClient(app).get("/")
    assert response.status_code == 404
