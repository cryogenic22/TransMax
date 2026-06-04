"""TMX-TM-2 — surface translation-memory reuse in the quality report.

The engine already bypasses the LLM for exact-match (TM) segments
(_separate_tm_matches). This makes that reuse VISIBLE: the report lists which
segments were served from TM, so users see 'reused, not re-translated'.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.core.constants import SubstitutionType
from app.agents.nodes.translation_engine import TranslationEngine


def _unit(seg_id, source):
    return SimpleNamespace(
        segment_id=seg_id,
        translation_source=source,
        gate_results={"violations": []},
        confidence_score=99.0,
    )


def test_report_surfaces_tm_reused_segments():
    eng = TranslationEngine()
    units = [
        _unit("1", SubstitutionType.TM_EXACT.value),   # reused from TM
        _unit("2", "llm_engine_v2"),                    # translated by LLM
        _unit("3", SubstitutionType.TM_EXACT.value),   # reused from TM
    ]

    class _Progress:
        failed = 0
        blocked = 0
        def to_dict(self):
            return {}

    report = eng._build_quality_report(units, _Progress(), duration=1.0)
    assert sorted(report["tm_reused_segments"]) == ["1", "3"]
    assert report["tm_reused_count"] == 2


def test_no_tm_reuse_when_all_llm():
    eng = TranslationEngine()
    units = [_unit("1", "llm_engine_v2"), _unit("2", "llm_engine_v2")]

    class _Progress:
        failed = 0
        blocked = 0
        def to_dict(self):
            return {}

    report = eng._build_quality_report(units, _Progress(), duration=1.0)
    assert report["tm_reused_segments"] == []
    assert report["tm_reused_count"] == 0
