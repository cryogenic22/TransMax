"""
TMX-V1-DURABLE-IR — stop the lossy v1 output rebuild (ADR-0008 hazard 2, half 1).

`app/api/v1/translations.py::get_job_result` used to reconstruct a job's full
text with `". ".join(s.translated_text or "" for s in segments)`. That
fabricates a ". " between every pair of segments regardless of what
punctuation (if any) the segment itself already carries, and it collapses
DOCX structural roles (headers, paragraphs, table cells — `element_type`)
into flat prose. For regulated content this is silent corruption of the
artefact (A3).

These tests prove:
  1. `_reconstruct_document_text` (the extracted pure helper) never emits a
     fabricated ". " when a segment already ends in terminal punctuation.
  2. It preserves structural boundaries recorded via `element_type` as a
     line break instead of folding them into running prose.
  3. The `/result` endpoint route actually calls the fixed helper (wiring
     regression guard), not just the helper in isolation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.database import Document, DocumentStatus, Segment
from app.api.v1.translations import _reconstruct_document_text

client = TestClient(app)


def _seg(text: str, element_type: str | None = None) -> Segment:
    """Build a detached Segment (no DB session needed for attribute access)."""
    return Segment(
        document_id="doc-1",
        order_index=0,
        source_text=text,
        translated_text=text,
        element_type=element_type,
        status="translated",
    )


# ---------------------------------------------------------------------------
# 1. Pure helper — varied terminal punctuation, no element_type structure.
# ---------------------------------------------------------------------------

def test_no_fabricated_period_after_question_mark():
    segments = [_seg("Is this correct?"), _seg("Yes it is.")]
    result = _reconstruct_document_text(segments)
    assert "?. " not in result
    assert result == "Is this correct? Yes it is."


def test_no_fabricated_period_after_colon():
    segments = [_seg("Please confirm:"), _seg("Confirmed")]
    result = _reconstruct_document_text(segments)
    assert ":. " not in result
    assert result == "Please confirm: Confirmed"


def test_varied_terminators_end_to_end_no_fabrication():
    segments = [
        _seg("Is this correct?"),
        _seg("Yes it is."),
        _seg("Please confirm:"),
        _seg("Confirmed"),
    ]
    result = _reconstruct_document_text(segments)
    # None of the source segments contained ". " glued onto their own
    # terminator — the old join fabricated one at every boundary.
    assert "?. " not in result
    assert ".. " not in result
    assert ":. " not in result
    assert result == "Is this correct? Yes it is. Please confirm: Confirmed"


# ---------------------------------------------------------------------------
# 2. Structural role (element_type) preserved as a real boundary, not prose.
# ---------------------------------------------------------------------------

def test_element_type_boundary_is_not_flattened_into_a_fabricated_period():
    segments = [
        _seg("Section Title", element_type="Header"),
        _seg("Body content here.", element_type="Paragraph"),
    ]
    result = _reconstruct_document_text(segments)
    # The old join would produce "Section Title. Body content here." —
    # inventing a period the title never had.
    assert "Section Title." not in result
    assert result == "Section Title\nBody content here."


def test_same_element_type_segments_join_with_space_not_period():
    segments = [
        _seg("First cell", element_type="TableCell"),
        _seg("second cell", element_type="TableCell"),
    ]
    result = _reconstruct_document_text(segments)
    assert ". " not in result
    assert result == "First cell second cell"


def test_empty_translated_text_segments_do_not_produce_double_separators():
    segments = [_seg("First."), _seg(""), _seg("Second.")]
    result = _reconstruct_document_text(segments)
    assert result == "First. Second."


# ---------------------------------------------------------------------------
# 3. Route wiring — /result must call the fixed helper, not the old join.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_init_db():
    with patch("app.main.init_db"):
        yield


def test_result_endpoint_does_not_fabricate_period_after_question_mark():
    from app.core.database import get_db

    doc = Document(
        id="job-durable-ir-1",
        name="doc.txt",
        source_language="en",
        target_language="fr",
        status=DocumentStatus.TRANSLATED.value,
        updated_at=datetime.now(timezone.utc),
    )
    segments = [
        Segment(
            document_id=doc.id,
            order_index=0,
            source_text="Is this correct?",
            translated_text="Est-ce correct ?",
            status="translated",
        ),
        Segment(
            document_id=doc.id,
            order_index=1,
            source_text="Yes it is.",
            translated_text="Oui, c'est ça.",
            status="translated",
        ),
    ]

    mock_db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        if model is Document:
            q.filter.return_value.first.return_value = doc
        elif model is Segment:
            q.filter.return_value.order_by.return_value.all.return_value = segments
        else:
            # QualityScorecard (and anything else the route queries) — no row.
            q.filter.return_value.first.return_value = None
        return q

    mock_db.query.side_effect = query_side_effect
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = client.get(f"/api/v1/translations/{doc.id}/result")
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 200
    translated_text = response.json()["translated_text"]
    assert "?. " not in translated_text
    assert translated_text == "Est-ce correct ? Oui, c'est ça."
