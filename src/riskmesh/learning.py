"""Trainable, explainable fraud classifier with time-safe feature engineering.

Uses standard-library SGD for regularized logistic regression, no remote models.
Training rows must have independently established labels; no synthetic accuracy
claim is a production fraud-detection guarantee.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from riskmesh.models import Transaction

FEATURES = (
    "log_amount",
    "sender_count_1h",
    "sender_amount_ratio",
    "novel_device",
    "novel_country",
    "receiver_in_degree_24h",
    "night_activity",
)


def extract_features(candidate: Transaction, history: list[Transaction]) -> dict[str, float]:
    """Only use same-tenant events strictly earlier than the candidate."""
    past = [
        t for t in history
        if t.tenant_id == candidate.tenant_id
        and t.timestamp < candidate.timestamp
        and t.transaction_id != candidate.transaction_id
    ]
    sender = [t for t in past if t.sender_account == candidate.sender_account]
    recent = [
        t for t in sender
        if t.timestamp - candidate.timestamp >= -timedelta(hours=1)
    ]
    inbound = {
        t.sender_account for t in past
        if t.receiver_account == candidate.receiver_account
        and t.timestamp - candidate.timestamp >= -timedelta(hours=24)
    }
    baseline = sorted(t.amount for t in sender)
    median = baseline[len(baseline) // 2] if baseline else candidate.amount
    return {
        "log_amount": math.log1p(candidate.amount),
        "sender_count_1h": math.log1p(len(recent)),
        "sender_amount_ratio": min(20.0, candidate.amount / max(1.0, median)),
        "novel_device": float(bool(sender) and candidate.device_id not in {t.device_id for t in sender}),
        "novel_country": float(bool(sender) and candidate.country not in {t.country for t in sender}),
        "receiver_in_degree_24h": math.log1p(len(inbound)),
        "night_activity": float(candidate.timestamp.hour < 5),
    }


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    z = math.exp(value)
    return z / (1 + z)


@dataclass
class LogisticModel:
    weights: list[float]
    bias: float
    means: list[float]
    scales: list[float]
    version: str = "sgd-logistic-v1"

    def probability(self, features: dict[str, float]) -> float:
        normalized = [
            (features[name] - mean) / scale
            for name, mean, scale in zip(FEATURES, self.means, self.scales, strict=True)
        ]
        return _sigmoid(self.bias + sum(w * x for w, x in zip(self.weights, normalized, strict=True)))

    def explain(self, features: dict[str, float]) -> list[dict]:
        contributions = [
            {
                "feature": name,
                "value": features[name],
                "log_odds_contribution": round(
                    weight * (features[name] - mean) / scale, 6
                ),
            }
            for name, weight, mean, scale in zip(
                FEATURES, self.weights, self.means, self.scales, strict=True
            )
        ]
        return sorted(contributions, key=lambda item: abs(item["log_odds_contribution"]), reverse=True)

    def as_dict(self) -> dict:
        return {
            "version": self.version,
            "features": list(FEATURES),
            "weights": self.weights,
            "bias": self.bias,
            "means": self.means,
            "scales": self.scales,
        }


def fit(
    examples: list[tuple[dict[str, float], int]],
    *,
    epochs: int = 120,
    learning_rate: float = 0.04,
    l2: float = 0.005,
) -> LogisticModel:
    if len(examples) < 12 or {label for _, label in examples} != {0, 1}:
        raise ValueError("Need at least 12 independently labeled examples from both classes")
    if not 1 <= epochs <= 2000 or not 0 < learning_rate <= 1:
        raise ValueError("Invalid training hyperparameters")
    n = len(examples)
    matrix = [[float(row[name]) for name in FEATURES] for row, _ in examples]
    if any(not math.isfinite(x) for row in matrix for x in row):
        raise ValueError("Non-finite training features")
    means = [sum(row[j] for row in matrix) / n for j in range(len(FEATURES))]
    scales = [
        max(1e-6, math.sqrt(sum((row[j] - means[j]) ** 2 for row in matrix) / n))
        for j in range(len(FEATURES))
    ]
    normalized = [
        [(row[j] - means[j]) / scales[j] for j in range(len(FEATURES))]
        for row in matrix
    ]
    weights = [0.0] * len(FEATURES)
    positive_rate = sum(label for _, label in examples) / n
    bias = math.log(positive_rate / (1 - positive_rate))
    for _ in range(epochs):
        gradients = [0.0] * len(FEATURES)
        bias_gradient = 0.0
        for row, (_, label) in zip(normalized, examples, strict=True):
            residual = _sigmoid(bias + sum(w * x for w, x in zip(weights, row, strict=True))) - label
            bias_gradient += residual
            for j, x in enumerate(row):
                gradients[j] += residual * x
        for j in range(len(weights)):
            weights[j] -= learning_rate * (gradients[j] / n + l2 * weights[j])
        bias -= learning_rate * bias_gradient / n
    return LogisticModel(weights, bias, means, scales)


def evaluate(model: LogisticModel, examples: list[tuple[dict[str, float], int]]) -> dict:
    if not examples:
        raise ValueError("Evaluation requires held-out labeled examples")
    probabilities = [model.probability(features) for features, _ in examples]
    labels = [label for _, label in examples]
    predicted = [p >= 0.5 for p in probabilities]
    tp = sum(p and y == 1 for p, y in zip(predicted, labels, strict=True))
    fp = sum(p and y == 0 for p, y in zip(predicted, labels, strict=True))
    fn = sum(not p and y == 1 for p, y in zip(predicted, labels, strict=True))
    tn = sum(not p and y == 0 for p, y in zip(predicted, labels, strict=True))
    return {
        "n": len(labels),
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
        "brier_score": sum((p - y) ** 2 for p, y in zip(probabilities, labels, strict=True)) / len(labels),
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
    }


def train_chronological(
    labeled: list[tuple[Transaction, int]],
    *,
    holdout_fraction: float = 0.25,
) -> tuple[LogisticModel, dict]:
    """Construct pre-event features and reserve the most recent events for evaluation."""
    if not 0.1 <= holdout_fraction <= 0.4:
        raise ValueError("Invalid holdout fraction")
    if len(labeled) < 24:
        raise ValueError("Need at least 24 labeled transactions")
    ordered = sorted(labeled, key=lambda item: (item[0].timestamp, item[0].transaction_id))
    examples = []
    history: list[Transaction] = []
    for transaction, label in ordered:
        if label not in (0, 1):
            raise ValueError("Labels must be zero or one")
        examples.append((extract_features(transaction, history), label))
        history.append(transaction)
    split = int(len(examples) * (1 - holdout_fraction))
    model = fit(examples[:split])
    return model, evaluate(model, examples[split:])


def save_signed_model(model: LogisticModel, path: str) -> None:
    """Write HMAC-authenticated model JSON; never deserialize executable pickle."""
    key = os.environ.get("RISK_MESH_MODEL_KEY", "")
    if len(key) < 32:
        raise ValueError("RISK_MESH_MODEL_KEY requires at least 32 characters")
    body = json.dumps(model.as_dict(), sort_keys=True, separators=(",", ":"))
    signature = hmac.new(key.encode(), body.encode(), hashlib.sha256).hexdigest()
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(".tmp")
    temp.write_text(json.dumps({"body": body, "signature": signature}), encoding="utf-8")
    os.replace(temp, destination)


def load_signed_model(path: str) -> LogisticModel:
    key = os.environ.get("RISK_MESH_MODEL_KEY", "")
    if len(key) < 32:
        raise ValueError("RISK_MESH_MODEL_KEY requires at least 32 characters")
    envelope = json.loads(Path(path).read_text(encoding="utf-8"))
    body = envelope["body"]
    signature = hmac.new(key.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, envelope["signature"]):
        raise ValueError("Model integrity verification failed")
    obj = json.loads(body)
    if obj["features"] != list(FEATURES) or len(obj["weights"]) != len(FEATURES):
        raise ValueError("Incompatible model schema")
    model = LogisticModel(obj["weights"], obj["bias"], obj["means"], obj["scales"])
    if any(not math.isfinite(x) for x in model.weights + model.means + model.scales + [model.bias]):
        raise ValueError("Invalid model parameters")
    if any(scale <= 0 for scale in model.scales):
        raise ValueError("Invalid model scales")
    return model
