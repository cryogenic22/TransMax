"""TMX-MQM-ENSEMBLE-RUN — multi-judge ensemble shadow runner.

Composition test: the runner loops the (mocked) judge, combines via the real
`aggregate_ensemble`, scores via the real engine, and reports escalation +
inter-judge κ + the honest single_lineage flag. No DB (job_id=None skips emit).
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.core.defect_taxonomy import DefectSeverity, MqmDimension
from app.core.mqm_annotation import MqmAnnotation
from app.agents.nodes import mqm_shadow


def _crit(seg, model="m1"):
    return MqmAnnotation(
        segment_id=seg,
        dimension=MqmDimension.ACCURACY,
        severity=DefectSeverity.CRITICAL,
        model_version=model,
    )


def _state():
    return {
        "job_id": None,  # skip the v2 emit branch — unit-test the logic only
        "segments": [
            {"segment_id": "s1", "source_text": "a b c", "translated_text": "x"},
            {"segment_id": "s2", "source_text": "d e f", "translated_text": "y"},
        ],
        "source_language": "en",
        "target_language": "fr",
    }


def _enable(monkeypatch, size=2, router=False):
    monkeypatch.setattr(
        mqm_shadow,
        "get_settings",
        lambda: SimpleNamespace(
            mqm_ensemble_shadow_enabled=True,
            mqm_ensemble_size=size,
            enable_llm_router=router,
        ),
    )


def test_disabled_returns_none():
    # Real settings: the flag defaults OFF, so the runner must no-op.
    assert asyncio.run(mqm_shadow.run_ensemble_shadow(_state())) is None


def test_agreeing_judges_merge_without_escalation(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(
        "app.services.mqm_judge.judge_segments",
        AsyncMock(side_effect=[[_crit("s1")], [_crit("s1")]]),
    )
    out = asyncio.run(mqm_shadow.run_ensemble_shadow(_state()))
    assert out is not None
    assert out["num_judges"] == 2
    assert out["merged_annotation_count"] == 1
    assert out["escalate"] is False
    assert out["single_lineage"] is True
    assert (
        out["inter_judge_kappa_first_pair"] == 1.0
    )  # both flag s1 over universe {s1,s2}


def test_disagreement_escalates_and_drops_kappa(monkeypatch):
    _enable(monkeypatch)
    # Judge A flags s1 Critical; judge B flags nothing — a real disagreement.
    monkeypatch.setattr(
        "app.services.mqm_judge.judge_segments",
        AsyncMock(side_effect=[[_crit("s1")], []]),
    )
    out = asyncio.run(mqm_shadow.run_ensemble_shadow(_state()))
    assert out["escalate"] is True
    assert out["merged_annotation_count"] == 1  # most-severe survives
    assert (
        out["inter_judge_kappa_first_pair"] == 0.0
    )  # chance-level agreement over the universe


def test_size_is_clamped_to_at_least_two(monkeypatch):
    _enable(monkeypatch, size=1)
    js = AsyncMock(side_effect=[[], []])
    monkeypatch.setattr("app.services.mqm_judge.judge_segments", js)
    out = asyncio.run(mqm_shadow.run_ensemble_shadow(_state()))
    assert out["num_judges"] == 2
    assert js.await_count == 2


def test_never_raises_when_judge_fails(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(
        "app.services.mqm_judge.judge_segments",
        AsyncMock(side_effect=RuntimeError("llm down")),
    )
    # Fail-safe: a judge failure must not propagate and must not change a verdict.
    assert asyncio.run(mqm_shadow.run_ensemble_shadow(_state())) is None


def test_no_translated_segments_returns_none(monkeypatch):
    _enable(monkeypatch)
    state = {"job_id": None, "segments": [{"segment_id": "s1", "source_text": "a"}]}
    assert asyncio.run(mqm_shadow.run_ensemble_shadow(state)) is None
