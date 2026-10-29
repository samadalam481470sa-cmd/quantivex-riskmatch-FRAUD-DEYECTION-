"""Tamper-evident signed risk decisions and canonical payload serialization."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone


def canonical_json(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sign_decision(payload: dict) -> dict:
    secret = os.getenv("RISK_MESH_SIGNING_KEY", "")
    if len(secret) < 32:
        raise ValueError("RISK_MESH_SIGNING_KEY must contain at least 32 characters")
    document = {
        "schema": "riskmesh.decision.v1",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    signature = hmac.new(secret.encode(), canonical_json(document), hashlib.sha256).hexdigest()
    return {"document": document, "signature": signature, "algorithm": "HMAC-SHA256"}


def verify_decision(envelope: dict) -> bool:
    secret = os.getenv("RISK_MESH_SIGNING_KEY", "")
    if len(secret) < 32:
        return False
    if envelope.get("algorithm") != "HMAC-SHA256":
        return False
    document = envelope.get("document")
    signature = envelope.get("signature")
    if not isinstance(document, dict) or not isinstance(signature, str):
        return False
    expected = hmac.new(secret.encode(), canonical_json(document), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
