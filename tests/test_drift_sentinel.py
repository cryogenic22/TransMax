"""TMX-DRIFT-SENTINEL — semantic-drift is None (not 0.0) when unavailable.

`calculate_semantic_drift` used to return `0.0` when it could not compute (no API
key / embed failure) — indistinguishable from a real catastrophic score, which
forced the drift gate to ignore every zero (A3 silent-default smell). It now
returns `None`, so "unavailable" and "real low score" are finally distinct, and
a genuine 0.0 correctly gates.
"""
from __future__ import annotations

from app.agents.nodes.reverse_translate import assess_reflexion
from app.services.quality_gate import QualityGateService


# ── AC-1: None when no key ──────────────────────────────────────────────


def test_drift_returns_none_without_key(monkeypatch) -> None:
    from app.core import config

    monkeypatch.setattr(config.settings, "openai_api_key", "")
    qg = QualityGateService()
    assert qg.calculate_semantic_drift("hola mundo", "hello world") is None


# ── AC-3: assess_reflexion — None excluded, real 0.0 gates ──────────────


def test_assess_gates_on_real_zero_excludes_none() -> None:
    out = assess_reflexion([{"validation_score": None}, {"validation_score": 0.0}])
    assert out["review_required"] is True
    assert out["n_assessed"] == 1
    assert out["min_score"] == 0.0


def test_assess_all_unavailable_not_held() -> None:
    # A job where drift could not be computed anywhere is NOT held on a non-signal.
    out = assess_reflexion([{"validation_score": None}, {"foo": "bar"}])
    assert out["review_required"] is False
    assert out["n_assessed"] == 0
    assert out["min_score"] is None
