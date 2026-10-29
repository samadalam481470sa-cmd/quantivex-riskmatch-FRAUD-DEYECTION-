from datetime import datetime, timedelta, timezone

import pytest

from riskmesh.learning import LogisticModel
from riskmesh.models import Transaction
from riskmesh.validation import validate_holdout


def example(i, label):
    return (
        Transaction(
            transaction_id=f"heldout-{i}",
            timestamp=datetime(2026, 6, 1, tzinfo=timezone.utc) + timedelta(minutes=i),
            tenant_id="test",
            sender_account=f"sender-{i % 5}",
            receiver_account=f"receiver-{i % 3}",
            amount=10000 if label else 20,
            currency="USD",
            device_id="device",
            source_ip="192.0.2.5",
            country="US",
            channel="api",
        ),
        label,
    )


def test_frozen_model_holdout_reports_uncertainty():
    model = LogisticModel([0.0] * 7, 0.0, [0.0] * 7, [1.0] * 7)
    labeled = [example(i, i % 5 == 0) for i in range(40)]
    result = validate_holdout(model, labeled, training_cutoff="2026-05-01T00:00:00Z")
    assert result["n"] == 40
    assert result["class_counts"] == {"fraud": 8, "legitimate": 32}
    assert 0 <= result["recall_wilson_95"][0] <= result["recall_wilson_95"][1] <= 1


def test_holdout_rejects_temporal_leakage_and_duplicate_ids():
    model = LogisticModel([0.0] * 7, 0.0, [0.0] * 7, [1.0] * 7)
    labeled = [example(i, i % 5 == 0) for i in range(40)]
    with pytest.raises(ValueError, match="overlaps"):
        validate_holdout(model, labeled, training_cutoff="2026-07-01T00:00:00Z")
    with pytest.raises(ValueError, match="Duplicate"):
        validate_holdout(model, labeled + [labeled[0]], training_cutoff="2026-05-01T00:00:00Z")
