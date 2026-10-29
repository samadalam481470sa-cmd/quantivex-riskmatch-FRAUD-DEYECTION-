from datetime import datetime, timedelta, timezone

import pytest

from riskmesh.learning import (
    evaluate,
    extract_features,
    fit,
    load_signed_model,
    save_signed_model,
    train_chronological,
)
from riskmesh.models import Transaction


def tx(index, *, tenant="alpha", amount=None):
    return Transaction(
        transaction_id=f"t{index}",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=index),
        tenant_id=tenant,
        sender_account="A",
        receiver_account="B",
        amount=amount if amount is not None else (20000 if index % 4 == 0 else 30),
        currency="USD",
        device_id="d1",
        source_ip="192.0.2.1",
        country="US",
        channel="api",
    )


def test_no_future_or_cross_tenant_feature_leakage():
    candidate = tx(10)
    baseline = extract_features(candidate, [tx(0)])
    assert extract_features(candidate, [tx(0), tx(11), tx(1, tenant="beta")]) == baseline


def test_train_evaluate_and_model_integrity(tmp_path, monkeypatch):
    labeled = [(tx(i), int(i % 4 == 0)) for i in range(60)]
    model, metrics = train_chronological(labeled)
    assert metrics["n"] == 15
    assert 0 <= metrics["brier_score"] <= 1
    assert 0 <= model.probability(extract_features(tx(61), [tx(i) for i in range(60)])) <= 1
    monkeypatch.setenv("RISK_MESH_MODEL_KEY", "unit-test-model-signing-secret-32-characters")
    path = tmp_path / "model.json"
    save_signed_model(model, str(path))
    assert load_signed_model(str(path)).weights == model.weights
    path.write_text(path.read_text().replace("sgd-logistic-v1", "modified-model-v1"))
    with pytest.raises(ValueError, match="integrity"):
        load_signed_model(str(path))


def test_fit_rejects_unlabeled_or_one_class():
    features = extract_features(tx(1), [])
    with pytest.raises(ValueError):
        fit([(features, 0)] * 15)
    with pytest.raises(ValueError):
        evaluate(fit([(features, i % 2) for i in range(12)]), [])
