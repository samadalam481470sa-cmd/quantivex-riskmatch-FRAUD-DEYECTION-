"""Defensive HMAC request signing with nonce-based replay prevention."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import sqlite3
import time
from pathlib import Path

from fastapi import HTTPException, Request


def signature(secret: str, method: str, path: str, timestamp: str,
              nonce: str, tenant: str, body: bytes) -> str:
    digest = hashlib.sha256(body).hexdigest()
    message = "\n".join([method.upper(), path, timestamp, nonce, tenant, digest])
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def reserve_nonce(tenant: str, nonce: str, now: int) -> bool:
    path = os.getenv("RISK_MESH_NONCE_DB", "/tmp/riskmesh_nonces.db")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE IF NOT EXISTS nonces "
                   "(tenant TEXT, nonce TEXT, created INTEGER, PRIMARY KEY(tenant,nonce))")
        db.execute("DELETE FROM nonces WHERE created < ?", (now - 600,))
        try:
            db.execute("INSERT INTO nonces VALUES (?,?,?)", (tenant, nonce, now))
        except sqlite3.IntegrityError:
            return False
    return True


async def authenticated_tenant(request: Request) -> str:
    tenant = request.headers.get("X-Risk-Tenant", "")
    timestamp = request.headers.get("X-Risk-Timestamp", "")
    nonce = request.headers.get("X-Risk-Nonce", "")
    supplied = request.headers.get("X-Risk-Signature", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", tenant):
        raise HTTPException(status_code=401, detail="Invalid tenant")
    if not re.fullmatch(r"[0-9]{10}", timestamp):
        raise HTTPException(status_code=401, detail="Invalid timestamp")
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", nonce):
        raise HTTPException(status_code=401, detail="Invalid nonce")
    if not re.fullmatch(r"[a-f0-9]{64}", supplied):
        raise HTTPException(status_code=401, detail="Invalid signature")
    now = int(time.time())
    if abs(now - int(timestamp)) > 300:
        raise HTTPException(status_code=401, detail="Expired request")
    configured = os.getenv("RISK_MESH_SIGNED_TENANT", "")
    secret = os.getenv("RISK_MESH_SIGNING_SECRET", "")
    if len(secret) < 32 or not configured:
        raise HTTPException(status_code=503, detail="Signed API not configured")
    if not hmac.compare_digest(tenant, configured):
        raise HTTPException(status_code=403, detail="Tenant not authorized")
    body = await request.body()
    if len(body) > 1048576:
        raise HTTPException(status_code=413, detail="Body too large")
    expected = signature(secret, request.method, request.url.path,
                         timestamp, nonce, tenant, body)
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")
    if not reserve_nonce(tenant, nonce, now):
        raise HTTPException(status_code=409, detail="Replay detected")
    return tenant


TENANT_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def production_mode() -> bool:
    return os.getenv("RISK_MESH_ENV", "development").lower() == "production"


def tenant_scope(requested: str) -> str:
    if not production_mode():
        return requested
    configured = os.getenv("RISK_MESH_TENANT_ID", "")
    if not TENANT_RE.fullmatch(configured):
        raise HTTPException(status_code=503, detail="Tenant authorization is not configured")
    if requested != configured:
        raise HTTPException(status_code=403, detail="Tenant access denied")
    return configured


def validate_runtime() -> None:
    if not production_mode():
        return
    key = os.getenv("RISK_MESH_API_KEY", "")
    tenant = os.getenv("RISK_MESH_TENANT_ID", "")
    if len(key) < 32 or not TENANT_RE.fullmatch(tenant):
        raise RuntimeError("Restricted mode requires a 32+ character API key and fixed tenant")
    if os.getenv("RISK_MESH_DB_PATH", "/tmp/riskmesh.db").startswith("/tmp/"):
        raise RuntimeError("Restricted mode requires persistent storage outside /tmp")
    if not all(os.getenv(name, "").startswith("https://") for name in ("RISK_MESH_OIDC_ISSUER", "RISK_MESH_OIDC_JWKS_URL")) or not os.getenv("RISK_MESH_OIDC_AUDIENCE"):
        raise RuntimeError("Restricted mode requires OIDC issuer, JWKS URL and audience")
    if os.getenv("RISK_MESH_ENABLE_DEMO", "false").lower() == "true":
        raise RuntimeError("Restricted mode cannot expose the demo dashboard")
