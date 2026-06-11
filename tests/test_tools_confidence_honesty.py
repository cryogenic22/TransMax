"""
TMX-TOOLS-CONF-HONEST + TMX-QDASH-CONTRACT — honest quality verdict from
the /api/tools universal translate endpoint.

Before this loop, a scoring failure left the hardcoded `confidence_score = 90.0`
/ `score_band = "High"` defaults in place, so a scoring OUTAGE rendered in the
UI as a green "90% · Ready for Review" (A3 fabrication on a regulator-facing
surface — same class as the QualityDashboard mock).

These tests pin:
- failure path: confidence is None, scoring_available False, band "Unavailable",
  needs_review True, breakdown_reasoning [], review_note explains the outage.
- success path: the response carries the engine's REAL breakdown_reasoning and
  score_breakdown components (not fabricated dimension scores).
"""
import asyncio


import app.api.tools as tools_mod
from app.api.tools import UniversalTranslateRequest


class _FakeMsg:
    def __init__(self, content):
        self.content = content


class _FakeLLM:
    def __init__(self, content):
        self._content = content

    async def ainvoke(self, _messages):
        return _FakeMsg(self._content)


def _patch_common(monkeypatch, llm_content):
    # LLM returns valid JSON segments
    monkeypatch.setattr(tools_mod, "get_llm", lambda: _FakeLLM(llm_content))
    # Constraints lookup must not touch the DB / embeddings
    monkeypatch.setattr(
        "app.services.db_service.DatabaseService.get_constraints",
        lambda self, *a, **k: {"glossary": [], "forbidden_terms": [], "tm_matches": []},
    )


def _run(req):
    return asyncio.run(tools_mod.universal_translate(req, user=object()))


def test_scoring_failure_returns_honest_unavailable(monkeypatch):
    _patch_common(monkeypatch, '{"segments":[{"source":"Hola","target":"Hello"}]}')

    # Force the scoring block to raise.
    def _boom(*a, **k):
        raise RuntimeError("embedding backend down")

    monkeypatch.setattr(
        "app.services.confidence_service.ConfidenceService.calculate_score", _boom
    )

    req = UniversalTranslateRequest(text="Hola", source_language="es", target_language="en")
    out = _run(req)

    assert out["translated_text"] == "Hello"
    # A3: no fabricated verdict on a scoring outage.
    assert out["scoring_available"] is False
    assert out["confidence"] is None
    assert out["score_band"] == "Unavailable"
    assert out["needs_review"] is True
    assert out["breakdown_reasoning"] == []
    assert "unavailable" in out["review_note"].lower()


def test_scoring_success_surfaces_real_breakdown_reasoning(monkeypatch):
    _patch_common(monkeypatch, '{"segments":[{"source":"Hola","target":"Hello"}]}')

    # Gate returns no violations (deterministic, no embeddings).
    class _Gate:
        def check_segment(self, *a, **k):
            return []

    monkeypatch.setattr(
        "app.services.quality_gate.get_quality_gate_service", lambda: _Gate()
    )

    from app.services.confidence_service import ScoreResult as _SR

    fake = _SR(
        final_score=92.0,
        band="High",
        status="REVIEW_REQUIRED",
        components={"base": 100.0, "deterministic_penalty": 8.0},
        breakdown_reasoning=["Defects: -8.0 (1 Major, 0 Minor)"],
    )
    monkeypatch.setattr(
        "app.services.confidence_service.ConfidenceService.calculate_score",
        lambda *a, **k: fake,
    )

    req = UniversalTranslateRequest(text="Hola", source_language="es", target_language="en")
    out = _run(req)

    assert out["scoring_available"] is True
    assert out["confidence"] == 92.0
    assert out["score_band"] == "High"
    # TMX-QDASH-CONTRACT: real reasoning + real penalty components surfaced.
    assert out["breakdown_reasoning"] == ["Defects: -8.0 (1 Major, 0 Minor)"]
    assert out["score_breakdown"]["base"] == 100.0
