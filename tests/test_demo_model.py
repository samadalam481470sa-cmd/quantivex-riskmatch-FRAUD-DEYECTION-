"""Validate the committed public demonstration model against its source generator."""
import os
import runpy
from pathlib import Path

from riskmesh.learning import load_signed_model, train_chronological

ROOT = Path(__file__).resolve().parents[1]
DEMO_KEY = "PUBLIC-DEMO-ONLY-NOT-A-SECRET-KEY-2026"


def test_committed_demo_model_loads_and_matches_retraining(monkeypatch):
    monkeypatch.setenv("RISK_MESH_MODEL_KEY", DEMO_KEY)
    committed = load_signed_model(str(ROOT / "models/synthetic-demo-model.json"))
    generator = runpy.run_path(str(ROOT / "scripts/build_demo_model.py"))
    retrained, metrics = train_chronological(generator["synthetic_transactions"]())
    assert len(committed.weights) == 7
    assert all(abs(a - b) < 1e-9 for a, b in zip(committed.weights, retrained.weights))
    assert abs(committed.bias - retrained.bias) < 1e-9
    assert metrics["n"] == 40


def test_demo_key_is_not_accepted_as_production_secret():
    assert "PUBLIC-DEMO-ONLY" in DEMO_KEY
    assert not os.getenv("RISK_MESH_MODEL_KEY") == DEMO_KEY
