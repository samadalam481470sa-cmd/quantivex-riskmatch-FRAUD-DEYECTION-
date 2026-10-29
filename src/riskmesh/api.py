"""Quantivex RiskMesh fraud-risk API for synthetic demonstration data."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from riskmesh.engine import batch_summary, exposure_score, score_transaction
from riskmesh.models import Transaction
from riskmesh.store import decisions, history, save

app = FastAPI(title="Quantivex RiskMesh", version="0.1.0")


def require_key(x_api_key: str | None = Header(default=None)) -> None:
    required = os.getenv("RISK_MESH_API_KEY")
    if not required or len(required) < 24:
        raise HTTPException(status_code=503, detail="Risk API key is not configured")
    if not secrets.compare_digest(required, x_api_key or ""):
        raise HTTPException(status_code=401, detail="Invalid API key")


class BatchRequest(BaseModel):
    transactions: list[Transaction] = Field(max_length=5000)


@app.get("/health")
def health():
    return {"status": "ok", "mode": "synthetic-fintech-prototype"}


@app.post("/api/v1/score", dependencies=[Depends(require_key)])
def score(transaction: Transaction):
    prior = history(transaction.tenant_id)
    result = score_transaction(transaction, prior)
    save(transaction, result)
    return result


@app.post("/api/v1/batch", dependencies=[Depends(require_key)])
def score_batch(payload: BatchRequest):
    results = []
    grouped: dict[str, list[Transaction]] = {}
    for transaction in payload.transactions:
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
    return {"decisions": decisions(x_tenant_id, limit)}


@app.get("/api/v1/exposure/{account}", dependencies=[Depends(require_key)])
def exposure(account: str, x_tenant_id: str = Header(min_length=1, max_length=64)):
    return exposure_score(history(x_tenant_id), account)


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(Path(__file__).with_name("dashboard.html"))
