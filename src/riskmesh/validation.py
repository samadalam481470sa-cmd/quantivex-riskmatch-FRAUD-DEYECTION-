"""Independent evaluation of a frozen fraud model on time-ordered labeled records.

No training occurs in this module. Holdout labels must come from an
independent, authorized source, not model-generated predictions.
"""
from __future__ import annotations

import math
from collections import Counter

from riskmesh.learning import LogisticModel, evaluate, extract_features
from riskmesh.models import Transaction


def validate_holdout(
    model: LogisticModel,
    labeled: list[tuple[Transaction, int]],
    *,
    training_cutoff: str,
    minimum_samples: int = 30,
) -> dict:
    """Evaluate on a strictly later holdout, including chronological history.

    Holdout records are intentionally NOT used as a feature history before
    their own timestamp; earlier holdout records can inform later features.
    """
    from datetime import datetime

    cutoff = datetime.fromisoformat(training_cutoff.replace("Z", "+00:00"))
    if cutoff.tzinfo is None:
        raise ValueError("Training cutoff must include a timezone")
    if len(labeled) < minimum_samples:
        raise ValueError("Insufficient holdout samples")
    ids = [transaction.transaction_id for transaction, _ in labeled]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate holdout transaction IDs")
    ordered = sorted(labeled, key=lambda item: (item[0].timestamp, item[0].transaction_id))
    if any(transaction.timestamp <= cutoff for transaction, _ in ordered):
        raise ValueError("Holdout overlaps training cutoff")
    if any(label not in (0, 1) for _, label in ordered):
        raise ValueError("Invalid holdout labels")
    counts = Counter(label for _, label in ordered)
    if len(counts) != 2:
        raise ValueError("Both fraud and legitimate holdout labels are required")
    history: list[Transaction] = []
    examples = []
    for transaction, label in ordered:
        features = extract_features(transaction, history)
        examples.append((features, label))
        history.append(transaction)
    metrics = evaluate(model, examples)
    # Wilson score interval for observed recall (binomial approximation).
    tp = metrics["confusion"]["tp"]
    fn = metrics["confusion"]["fn"]
    n = tp + fn
    z = 1.96
    p = tp / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    metrics["recall_wilson_95"] = [max(0.0, center - radius), min(1.0, center + radius)]
    metrics["class_counts"] = {"fraud": counts[1], "legitimate": counts[0]}
    metrics["training_cutoff"] = cutoff.isoformat()
    metrics["validation_kind"] = "frozen-model-temporal-holdout"
    return metrics
