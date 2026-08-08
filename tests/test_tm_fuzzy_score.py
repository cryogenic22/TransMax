"""TMX-TM-FUZZY-HONEST — the fuzzy-TM path must report the REAL score.

A3: no unearned claims. A similarity score presented to a reviewer (or the
seam TM, ADR-0009) must be derived from the cosine distance the query
actually computed — never a hardcoded constant. These tests are written
red-first against the fabricated ``"score": 0.9``.

They run WITHOUT Postgres/pgvector: the pure mapping is tested directly and
the fuzzy path is exercised with a stubbed session + stubbed embeddings
module, so SQLite CI covers them.
"""

import sys
import types
from types import SimpleNamespace
from typing import List
from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.core.constants import SubstitutionType
from app.services.db_service import DatabaseService


# ── Pure mapping: distance → score ──────────────────────────────────────────
# Imported inside each test so a missing symbol fails THAT test, not
# collection of the whole module (keeps the path test's red signal visible).


def test_fuzzy_score_zero_distance_is_perfect() -> None:
    from app.services.db_service import _fuzzy_score

    assert _fuzzy_score(0.0) == 1.0


def test_fuzzy_score_is_one_minus_distance() -> None:
    from app.services.db_service import _fuzzy_score

    assert _fuzzy_score(0.04) == pytest.approx(0.96)
    assert _fuzzy_score(0.25) == pytest.approx(0.75)


def test_fuzzy_score_reports_negative_similarity_honestly() -> None:
    # Cosine distance spans [0, 2]; similarity spans [-1, 1]. No clamping:
    # the score is what the geometry says (A3 — never manufacture a value).
    from app.services.db_service import _fuzzy_score

    assert _fuzzy_score(2.0) == pytest.approx(-1.0)


def test_fuzzy_score_rejects_impossible_distances() -> None:
    from app.services.db_service import _fuzzy_score

    with pytest.raises(ValueError):
        _fuzzy_score(-0.01)
    with pytest.raises(ValueError):
        _fuzzy_score(2.01)


def test_assemble_fuzzy_match_shape_and_score() -> None:
    from app.services.db_service import _assemble_fuzzy_match

    result = _assemble_fuzzy_match("Hello world", "Bonjour le monde", 0.07)
    assert result == {
        "source": "Hello world",
        "target": "Bonjour le monde",
        "score": pytest.approx(0.93),
        "type": SubstitutionType.TM_FUZZY.value,
    }


# ── Fuzzy path: score populated from the row's distance ─────────────────────


def _stub_langchain_openai(
    monkeypatch: pytest.MonkeyPatch, vector: List[float]
) -> None:
    """Make ``from langchain_openai import OpenAIEmbeddings`` yield a stub
    that never touches the network."""
    module = types.ModuleType("langchain_openai")

    class _StubEmbeddings:
        def __init__(self, api_key: object = None) -> None:
            self._api_key = api_key

        def embed_query(self, text: str) -> List[float]:
            return vector

    setattr(module, "OpenAIEmbeddings", _StubEmbeddings)
    monkeypatch.setitem(sys.modules, "langchain_openai", module)


def test_fuzzy_path_score_derives_from_row_distance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the nearest row at cosine distance 0.04, the returned score must
    be 0.96 — NOT the fabricated 0.9."""
    service = DatabaseService()
    mock_session = MagicMock()
    monkeypatch.setattr(service, "get_session", MagicMock(return_value=mock_session))
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-stub-key")
    monkeypatch.setattr(settings, "enable_live_llm_inference", True)  # opt into the (stubbed) embeddings path
    _stub_langchain_openai(monkeypatch, [0.0] * 1536)

    # Exact-hash lookup misses -> the fuzzy branch runs.
    mock_session.query.return_value.filter.return_value.first.return_value = None
    # Fuzzy query returns the nearest row WITH its cosine distance.
    row = SimpleNamespace(
        source_text="Hello world",
        target_text="Bonjour le monde",
        distance=0.04,
    )
    mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = row

    match = service.find_best_match("Hello worlds", "en", "fr")

    assert match is not None, "fuzzy path returned no match"
    assert match["type"] == SubstitutionType.TM_FUZZY.value
    assert match["score"] == pytest.approx(1.0 - 0.04), (
        f"score must derive from the row's cosine distance (expected 0.96), "
        f"got {match['score']!r}"
    )


def test_fuzzy_path_perfect_row_scores_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """A row at distance 0.0 must score 1.0 — the constant 0.9 would
    under-report a perfect semantic match."""
    service = DatabaseService()
    mock_session = MagicMock()
    monkeypatch.setattr(service, "get_session", MagicMock(return_value=mock_session))
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-stub-key")
    monkeypatch.setattr(settings, "enable_live_llm_inference", True)  # opt into the (stubbed) embeddings path
    _stub_langchain_openai(monkeypatch, [0.0] * 1536)

    mock_session.query.return_value.filter.return_value.first.return_value = None
    row = SimpleNamespace(source_text="a", target_text="b", distance=0.0)
    mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = row

    match = service.find_best_match("a!", "en", "fr")

    assert match is not None
    assert match["score"] == pytest.approx(1.0)
