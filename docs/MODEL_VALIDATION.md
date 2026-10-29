# Independent fraud-model validation protocol

**Current state: NOT independently validated.** The checked-in synthetic model
demonstrates software correctness, not real fraud recall, precision or fairness.

1. Obtain a lawful, documented, consent-appropriate labeled dataset with
   provenance, label delay, missingness, class prevalence and jurisdiction.
2. Freeze a holdout period **after** training and model selection; isolate
   entities and avoid leakage from future graph edges, chargeback outcomes,
   investigation results, or label-dependent features.
3. Appoint an evaluator separate from model development and pre-register
   decision thresholds and false-positive constraints.
4. Compare against rule-only baseline, graph-only model, logistic ML-only
   model, and the combined approach on identical holdout records.
5. Report PR-AUC, ROC-AUC, precision, recall, FPR, FNR, confusion matrix,
   Brier score, calibration curves, confidence intervals, and throughput/
   p95/p99 latency at each threshold. Report prevalence and class counts.
6. Slice results by payment channel, amount band, customer tenure,
   country/region, device novelty and other legally appropriate cohorts;
   investigate unequal error rates without using protected traits for
   adverse decisions.
7. Simulate delayed labels, concept drift, adversarial account rings,
   micro-transaction fraud, benign high-velocity transfers, data poisoning,
   replayed requests, and coordinated graph attacks.
8. Require analyst review, rollback procedures, incident playbooks and
   monitored shadow deployment before considering automated enforcement.

**Acceptance is not established by the synthetic 100% precision/recall demo.**
No independent validation or external benchmark is claimed.
