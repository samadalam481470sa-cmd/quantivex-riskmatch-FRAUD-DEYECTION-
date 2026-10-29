"""Train a signed ML model on labeled local JSONL transactions.

Usage:
  RISK_MESH_MODEL_KEY=<32+-character-secret> \
    python scripts/train_model.py labeled.jsonl model.json

JSONL rows: {"transaction": {Transaction fields}, "fraud_label": 0 or 1}
Never train on unlabeled production data or report synthetic scores as real accuracy.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from riskmesh.learning import save_signed_model, train_chronological
from riskmesh.models import Transaction


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: train_model.py labeled.jsonl model.json")
    source = Path(sys.argv[1])
    if source.stat().st_size > 20_000_000:
        raise SystemExit("Training file too large")
    rows = [
        json.loads(line)
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) > 50_000:
        raise SystemExit("Training row limit exceeded")
    labeled = [
        (Transaction.model_validate(row["transaction"]), int(row["fraud_label"]))
        for row in rows
    ]
    model, metrics = train_chronological(labeled)
    save_signed_model(model, sys.argv[2])
    print(json.dumps({"model": model.version, "holdout_metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()
