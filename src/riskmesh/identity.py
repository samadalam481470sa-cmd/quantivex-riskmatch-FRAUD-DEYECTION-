"""OIDC access-token verification with pinned issuer/audience and RBAC.

Only RS256 is accepted. JWT claims are never trusted before signature validation.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

import jwt
from fastapi import HTTPException, Request
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError

from riskmesh.security import production_mode

_ROLES = {"viewer", "analyst", "admin"}
_TENANT = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant: str
    role: str


def verify_token(token: str) -> Principal:
    issuer = os.getenv("RISK_MESH_OIDC_ISSUER", "")
    audience = os.getenv("RISK_MESH_OIDC_AUDIENCE", "")
    jwks = os.getenv("RISK_MESH_OIDC_JWKS_URL", "")
    if not issuer.startswith("https://") or not audience or not jwks.startswith("https://"):
        raise HTTPException(status_code=503, detail="OIDC verifier is not configured")
    if len(token) > 8192:
        raise HTTPException(status_code=401, detail="Invalid access token")
    try:
        key = PyJWKClient(jwks, cache_jwk_set=True, lifespan=300, timeout=5).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token, key.key, algorithms=["RS256"], issuer=issuer, audience=audience,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            leeway=30,
        )
    except (PyJWTError, ValueError, OSError) as exc:
        raise HTTPException(status_code=401, detail="Invalid access token") from exc
    tenant = claims.get("tenant_id")
    role = claims.get("riskmesh_role")
    subject = claims.get("sub")
    if not isinstance(tenant, str) or not _TENANT.fullmatch(tenant):
        raise HTTPException(status_code=403, detail="Missing tenant claim")
    if role not in _ROLES or not isinstance(subject, str) or not subject:
        raise HTTPException(status_code=403, detail="Missing role or subject claim")
    return Principal(subject, tenant, role)


def authorize(request: Request, minimum_role: str = "viewer") -> Principal | None:
    if not production_mode():
        return None
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    principal = verify_token(header[7:])
    if {"viewer": 0, "analyst": 1, "admin": 2}[principal.role] < {
        "viewer": 0, "analyst": 1, "admin": 2
    }[minimum_role]:
        raise HTTPException(status_code=403, detail="Insufficient role")
    configured = os.getenv("RISK_MESH_TENANT_ID", "")
    if principal.tenant != configured:
        raise HTTPException(status_code=403, detail="Tenant access denied")
    return principal
