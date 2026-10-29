"""Public, read-only fraud demonstrations using generated, immutable synthetic data.

The endpoint does not accept transaction payloads, access the database, ingest
personal information, train models or trigger financial decisions.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from riskmesh.engine import score_transaction
from riskmesh.models import Transaction
from riskmesh.temporal import combine_risk, investigate

_BASE = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
CASES = (
    {"id": "legitimate", "name": "Legitimate payment", "category": "Behavioral baseline",
     "description": "A familiar device and normal spending pattern"},
    {"id": "amount-spike", "name": "Unusual high-value transfer", "category": "Behavioral anomaly",
     "description": "An unfamiliar device, country shift and extreme amount outlier"},
    {"id": "circular-ring", "name": "Circular funding ring", "category": "Temporal graph",
     "description": "Time-ordered transfers complete a suspicious funding cycle"},
    {"id": "layering", "name": "Rapid account layering", "category": "Graph aggregation",
     "description": "Several unrelated accounts fund one quick outbound transfer"},
)


def _tx(i: str, minute: int, sender: str, receiver: str, amount: float,
        *, device: str = "trusted-device", country: str = "US") -> Transaction:
    return Transaction(
        transaction_id=f"synthetic-{i}",
        timestamp=_BASE + timedelta(minutes=minute),
        tenant_id="public-synthetic-demo",
        sender_account=sender,
        receiver_account=receiver,
        amount=amount,
        currency="USD",
        device_id=device,
        source_ip="192.0.2.10",
        country=country,
        channel="api",
    )


def scenario(case_id: str) -> tuple[Transaction, list[Transaction]]:
    if case_id == "legitimate":
        history = [
            _tx("normal-1", 1, "acct-100", "shop-1", 95),
            _tx("normal-2", 2, "acct-100", "shop-2", 105),
            _tx("normal-3", 3, "acct-100", "shop-3", 100),
        ]
        return _tx("normal-current", 15, "acct-100", "shop-4", 106), history
    if case_id == "amount-spike":
        history = [
            _tx("base-1", 1, "acct-200", "shop-1", 100),
            _tx("base-2", 2, "acct-200", "shop-2", 110),
            _tx("base-3", 3, "acct-200", "shop-3", 105),
        ]
        return _tx(
            "suspicious-current", 16, "acct-200", "acct-foreign", 19000,
            device="unknown-device", country="GB",
        ), history
    if case_id == "circular-ring":
        history = [
            _tx("ring-base-1", 0, "acct-a", "merchant-1", 100),
            _tx("ring-b-c", 1, "acct-b", "acct-c", 25000),
            _tx("ring-c-a", 2, "acct-c", "acct-a", 25000),
            _tx("ring-base-2", 3, "acct-a", "merchant-2", 120),
            _tx("ring-base-3", 4, "acct-a", "merchant-3", 110),
        ]
        return _tx(
            "ring-current", 18, "acct-a", "acct-b", 25000,
            device="unknown-device", country="GB",
        ), history
    if case_id == "layering":
        history = [
            _tx("source-1", 1, "source-a", "consolidator", 20000),
            _tx("source-2", 2, "source-b", "consolidator", 20000),
            _tx("source-3", 3, "source-c", "consolidator", 20000),
        ]
        return _tx("outbound", 12, "consolidator", "destination", 55000), history
    raise KeyError("Unknown synthetic investigation")


def analyze(case_id: str) -> dict:
    candidate, prior = scenario(case_id)
    baseline = score_transaction(candidate, prior)
    motifs = investigate(candidate, prior)
    score = combine_risk(baseline.risk_score, motifs)
    decision = "block" if score >= 70 else "review" if score >= 35 else "allow"
    title = next(case for case in CASES if case["id"] == case_id)
    return {
        "case": title,
        "transaction_id": candidate.transaction_id,
        "amount": candidate.amount,
        "currency": candidate.currency,
        "risk_score": score,
        "baseline_score": baseline.risk_score,
        "decision": decision,
        "behavioral_signals": [s.model_dump() for s in baseline.signals],
        "temporal_graph_findings": [m.as_dict() for m in motifs],
        "transfers": [
            {
                "sender": tx.sender_account,
                "receiver": tx.receiver_account,
                "amount": tx.amount,
                "minute": int((tx.timestamp - _BASE).total_seconds() // 60),
                "candidate": tx.transaction_id == candidate.transaction_id,
            }
            for tx in [*prior, candidate]
        ],
        "data_source": "fixed-synthetic-only",
        "enforcement": "disabled",
        "model_version": "temporal-graph-v1",
    }
