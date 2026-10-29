# Independent fraud-model validation protocol

**Current state: NOT independently validated.** The checked-in synthetic model
demonstrates software correctness, not real fraud recall, precision or fairness.

A **frozen-model temporal holdout evaluator** is implemented in
`src/riskmesh/validation.py` and `scripts/evaluate_holdout.py`.
It rejects duplicate transaction IDs, overlap with the supplied training
cutoff, missing class diversity and insufficient samples; it reports a
Wilson 95% interval for recall in addition to confusion-matrix metrics.

```bash
RISK_MESH_MODEL_KEY="your-private-model-key" \
  python scripts/evaluate_holdout.py model.json independent_holdout.jsonl 2026-05-01T00:00:00Z
```

Holdout JSONL lines have the form
`{"transaction": { ... Transaction fields ... }, "fraud_label": 0}`
(or `fraud_label: 1`). **Use only lawfully acquired, independently labeled
records.** No real-world dataset is bundled. The evaluator begins with an
empty history, so it does not currently incorporate pre-cutoff history and
cannot substitute for a full feature-store replay.

Required independent assessment:

1. Freeze the model and decision thresholds *before* opening the holdout.
2. Record data provenance, delayed labels, class prevalence, missingness,
   and exact split boundaries.
3. Assign an independent reviewer who did not select the model parameters.
4. Compare rules-only, graph-only, ML-only and combined systems on identical
   authorized records, at fixed false-positive constraints.
5. Report PR-AUC, ROC-AUC, precision, recall, FPR, FNR, calibration,
   confidence intervals, p95/p99 latency, drift and operational costs.
6. Assess benign high velocity, coordinated microfraud, account rings,
   false-positive harm, evasion and data poisoning.
7. Run a monitored shadow deployment, document incident/rollback processes
   and obtain required privacy and regulatory signoffs.

**Synthetic 100% precision/recall is not real-world validation.**
