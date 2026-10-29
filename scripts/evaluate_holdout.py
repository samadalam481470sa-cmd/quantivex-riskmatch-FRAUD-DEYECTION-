"""Evaluate a frozen signed model on independent labeled JSONL.

Usage: python scripts/evaluate_holdout.py MODEL.json HOLDOUT.jsonl 2026-01-01T00:00:00Z
Requires RISK_MESH_MODEL_KEY. Does not retrain or modify the model.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from riskmesh.learning import load_signed_model
from riskmesh.models import Transaction
from riskmesh.validation import validate_holdout


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("Usage: evaluate_holdout.py MODEL HOLDOUT_JSONL TRAINING_CUTOFF")
    model = load_signed_model(sys.argv[1])
    path = Path(sys.argv[2])
    if path.stat().st_size > 20_000_000:
        raise SystemExit("Holdout too large")
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(records) > 50000:
        raise SystemExit("Holdout row limit exceeded")
    labeled = [
        (Transaction.model_validate(row["transaction"]), row["fraud_label"])
        for row in records
    ]
    metrics = validate_holdout(model, labeled, training_cutoff=sys.argv[3])
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
