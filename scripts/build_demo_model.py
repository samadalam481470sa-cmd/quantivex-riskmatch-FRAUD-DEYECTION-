"""Reproduce the public synthetic demonstration model; never use for real payments.

Run:
    python scripts/build_demo_model.py
This script uses a deliberately PUBLIC demo integrity key. It is not a secret.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from riskmesh.learning import save_signed_model, train_chronological
from riskmesh.models import Transaction

DEMO_KEY = "PUBLIC-DEMO-ONLY-NOT-A-SECRET-KEY-2026"


def synthetic_transactions():
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(160):
        fraud = int(i % 7 == 0 or i % 13 == 0)
        amount = (4500 + i * 41) if fraud else (30 + i % 23)
        transaction = Transaction(
            transaction_id=f"synthetic-{i:04d}",
            timestamp=base + timedelta(minutes=i * 3),
            tenant_id="synthetic-demo",
            sender_account=f"account-{i % 8}",
            receiver_account=f"merchant-{(i * 3) % 17}",
            amount=amount,
            currency="USD",
            device_id=f"device-{i % 8}" if not fraud else f"unfamiliar-{i}",
            source_ip="192.0.2.10",
            country="US" if not fraud else "GB",
            channel="api",
        )
        rows.append((transaction, fraud))
    return rows


def main():
    model, metrics = train_chronological(synthetic_transactions())
    output = Path("models/synthetic-demo-model.json")
    os.environ["RISK_MESH_MODEL_KEY"] = DEMO_KEY
    save_signed_model(model, str(output))
    metrics_path = Path("models/synthetic-demo-metrics.json")
    metrics_path.write_text(
        json.dumps(
            {
                "dataset": "deterministic synthetic demonstration labels",
                "not_real_world_validation": True,
                "training_examples": 120,
                "holdout_examples": 40,
                "metrics": metrics,
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
