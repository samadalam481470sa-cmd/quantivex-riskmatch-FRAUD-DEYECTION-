"""Quantivex RiskMesh fraud-risk API for synthetic demonstration data."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from riskmesh.attestation import sign_decision, verify_decision
from riskmesh.demo import CASES, analyze
from riskmesh.engine import batch_summary, exposure_score, score_transaction
from riskmesh.identity import authorize
from riskmesh.learning import extract_features, load_signed_model
from riskmesh.models import Transaction
from riskmesh.security import production_mode, tenant_scope, validate_runtime
from riskmesh.store import decisions, history, save
from riskmesh.telemetry import metrics_response, record
from riskmesh.temporal import combine_risk, investigate

validate_runtime()
app = FastAPI(title="Quantivex RiskMesh", version="0.2.0", docs_url=None if production_mode() else "/docs", redoc_url=None)


def require_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    if production_mode():
        authorize(request, "analyst")
        return
    required = os.getenv("RISK_MESH_API_KEY")
    if not required or len(required) < 24:
        raise HTTPException(status_code=503, detail="Risk API key is not configured")
    if not secrets.compare_digest(required, x_api_key or ""):
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    if production_mode() and request.url.path.startswith("/api/"):
        if int(request.headers.get("content-length", "0") or "0") > 1_048_576:
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Request too large"}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'self'; object-src 'none'; frame-ancestors 'none'"
    record(request.url.path, response.status_code)
    return response


@app.get("/internal/metrics", include_in_schema=False)
def internal_metrics(request: Request):
    if production_mode():
        authorize(request, "admin")
    else:
        require_key(request, request.headers.get("X-API-Key"))
    return metrics_response()


class BatchRequest(BaseModel):
    transactions: list[Transaction] = Field(max_length=5000)


@app.get("/health")
def health():
    return {"status": "ok", "mode": "restricted" if production_mode() else "synthetic-fintech-prototype"}


@app.post("/api/v1/score", dependencies=[Depends(require_key)])
def score(transaction: Transaction):
    tenant_scope(transaction.tenant_id)
    prior = history(transaction.tenant_id)
    result = score_transaction(transaction, prior)
    save(transaction, result)
    return result


@app.post("/api/v1/batch", dependencies=[Depends(require_key)])
def score_batch(payload: BatchRequest):
    results = []
    grouped: dict[str, list[Transaction]] = {}
    for transaction in payload.transactions:
        tenant_scope(transaction.tenant_id)
        grouped.setdefault(transaction.tenant_id, history(transaction.tenant_id))
        result = score_transaction(transaction, grouped[transaction.tenant_id])
        save(transaction, result)
        grouped[transaction.tenant_id].append(transaction)
        results.append(result)
    return {
        "summary": batch_summary(results),
        "results": [item.model_dump() for item in results],
    }


@app.get("/api/v1/decisions", dependencies=[Depends(require_key)])
def recent_decisions(
    x_tenant_id: str = Header(min_length=1, max_length=64),
    limit: int = Query(default=50, ge=1, le=100),
):
    tenant_scope(x_tenant_id)
    return {"decisions": decisions(x_tenant_id, limit)}


@app.get("/api/v1/exposure/{account}", dependencies=[Depends(require_key)])
def exposure(account: str, x_tenant_id: str = Header(min_length=1, max_length=64)):
    tenant_scope(x_tenant_id)
    return exposure_score(history(x_tenant_id), account)


@app.get("/api/v1/demo/cases", include_in_schema=False)
def demo_cases():
    if production_mode():
        raise HTTPException(status_code=404, detail="Not found")
    return {"cases": CASES, "mode": "synthetic-read-only"}


@app.get("/api/v1/demo/investigate/{case_id}", include_in_schema=False)
def demo_investigate(case_id: str):
    if production_mode():
        raise HTTPException(status_code=404, detail="Not found")
    try:
        return analyze(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown demo case") from exc


@app.get("/assets/dashboard.css", include_in_schema=False)
def dashboard_style():
    if production_mode():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(Path(__file__).with_name("dashboard.css"), media_type="text/css")


@app.get("/assets/dashboard.js", include_in_schema=False)
def dashboard_script():
    if production_mode():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(Path(__file__).with_name("dashboard.js"), media_type="text/javascript")


@app.get("/", include_in_schema=False)
def dashboard():
    if production_mode() and os.getenv("RISK_MESH_ENABLE_DEMO", "").lower() != "true":
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(Path(__file__).with_name("dashboard.html"))


class VerifyRequest(BaseModel):
    envelope: dict


@app.post("/api/v1/advanced/investigate", dependencies=[Depends(require_key)])
def advanced_investigate(transaction: Transaction):
    """Run temporal motifs and return a cryptographically attested risk explanation."""
    tenant_scope(transaction.tenant_id)
    prior = history(transaction.tenant_id)
    baseline = score_transaction(transaction, prior)
    motifs = investigate(transaction, prior)
    fused_score = combine_risk(baseline.risk_score, motifs)
    decision = "block" if fused_score >= 70 else "review" if fused_score >= 35 else "allow"
    report = {
        "tenant_id": transaction.tenant_id,
        "transaction_id": transaction.transaction_id,
        "base_risk_score": baseline.risk_score,
        "risk_score": fused_score,
        "decision": decision,
        "behavioral_signals": [signal.model_dump() for signal in baseline.signals],
        "temporal_graph_findings": [finding.as_dict() for finding in motifs],
        "model_version": "temporal-graph-v1",
    }
    try:
        envelope = sign_decision(report)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    # Save only after successful scoring and attestation.
    save(transaction, baseline.model_copy(update={"risk_score": fused_score, "decision": decision}))
    return envelope


@app.post("/api/v1/advanced/verify", dependencies=[Depends(require_key)])
def verify_attestation(payload: VerifyRequest):
    return {"valid": verify_decision(payload.envelope)}


@app.post("/api/v1/ml/score", dependencies=[Depends(require_key)])
def ml_score(transaction: Transaction):
    """Run the independently trained model in shadow/analyst mode."""
    model_path = os.getenv("RISK_MESH_MODEL_PATH")
    if not model_path:
        raise HTTPException(status_code=503, detail="No signed model configured")
    try:
        model = load_signed_model(model_path)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="Signed model unavailable or invalid") from exc
    tenant_scope(transaction.tenant_id)
    features = extract_features(transaction, history(transaction.tenant_id))
    probability = model.probability(features)
    return {
        "transaction_id": transaction.transaction_id,
        "model_version": model.version,
        "fraud_probability": round(probability, 6),
        "feature_contributions": model.explain(features),
        "mode": "shadow",
        "action": "analyst_review_only",
    }
