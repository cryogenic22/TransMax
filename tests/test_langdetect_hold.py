"""TMX-LANGDETECT-HOLD — uncertain source language becomes an explicit hold,
never a silent "en" (A3, red-stop RS-06, reSCApe seam invariant C-3).

TMX-SSOT-TIER made the DECLARED ``Document.source_language`` authoritative:
that path must stay byte-identical (AC-3). The hold applies ONLY when there
is no declared language AND detection is low-confidence or errored:

  - AC-1: no declared language + low-confidence detection -> hold, no "en"
  - AC-2: no declared language + detector raises -> same hold, no crash
  - AC-3: declared language present -> completely unchanged, detector unused
  - AC-4: the v2 audit event fires with confidence + a typed reason, BEFORE
    the state flags are set
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_db_mock(*, doc_meta: dict[str, str], segments: list[dict[str, str]]) -> MagicMock:
    mock_db = MagicMock()
    mock_db.get_document_status.return_value = "UPLOADED"
    mock_db.get_document_metadata.return_value = doc_meta
    mock_db.get_segments_for_doc.return_value = segments
    return mock_db


def _make_audit_mock() -> MagicMock:
    mock_audit = MagicMock()
    mock_audit.create_audit_trail.return_value = "audit-1"
    return mock_audit


# ── AC-1: low-confidence detection holds the job, never "en" ────────────


@patch("app.services.language_detection.detect_language")
@patch("app.agents.graph._emit_v2_audit_event")
@patch("app.agents.graph.get_audit_service")
@patch("app.agents.graph.get_db_service")
async def test_low_confidence_detection_holds_not_en(
    mock_db_svc: MagicMock,
    mock_audit_svc: MagicMock,
    mock_v2_emit: MagicMock,
    mock_detect: MagicMock,
) -> None:
    mock_db_svc.return_value = _make_db_mock(
        doc_meta={},  # no declared source language
        segments=[{"source_text": "Ceci ressemble a du texte ambigu et incertain."}],
    )
    mock_audit_svc.return_value = _make_audit_mock()

    detection = MagicMock()
    detection.language = "und"
    detection.confidence = 0.31
    detection.low_confidence = True
    detection.reason = "low_confidence"
    mock_detect.return_value = detection

    from app.agents.graph import decide_after_validate, validate_request

    state = {"doc_id": "doc-1", "target_language": "es", "job_id": "job-1"}
    await validate_request(state)

    # The core failure mode: source_language must NEVER become "en" here.
    assert state.get("source_language") != "en", (
        f"source_language silently defaulted to 'en': {state.get('source_language')!r}"
    )
    assert state.get("source_language_confirmation_required") is True
    assert state.get("source_language_detection_confidence") == 0.31
    assert state.get("source_language_detection_reason") == "low_confidence"

    # AC-4: the v2 audit event carries confidence + a typed reason.
    hold_calls = [
        c for c in mock_v2_emit.call_args_list
        if c.kwargs.get("event_type") == "SOURCE_LANGUAGE_CONFIRMATION_REQUIRED"
    ]
    assert len(hold_calls) == 1, f"expected exactly one hold audit event, got {len(hold_calls)}"
    payload = hold_calls[0].kwargs["payload"]
    assert payload["detection_confidence"] == 0.31
    assert payload["reason"] == "low_confidence"

    # No segment is ever translated: the graph routes straight to finalize.
    assert decide_after_validate(state) == "finalize"


# ── AC-2: detector raising is held, not crashed, not "en" ───────────────


@patch("app.services.language_detection.detect_language")
@patch("app.agents.graph._emit_v2_audit_event")
@patch("app.agents.graph.get_audit_service")
@patch("app.agents.graph.get_db_service")
async def test_detector_error_holds_no_crash(
    mock_db_svc: MagicMock,
    mock_audit_svc: MagicMock,
    mock_v2_emit: MagicMock,
    mock_detect: MagicMock,
) -> None:
    mock_db_svc.return_value = _make_db_mock(
        doc_meta={},
        segments=[{"source_text": "Some sample text that is long enough to attempt detection."}],
    )
    mock_audit_svc.return_value = _make_audit_mock()
    mock_detect.side_effect = RuntimeError("detector exploded")

    from app.agents.graph import decide_after_validate, validate_request

    state = {"doc_id": "doc-2", "target_language": "es", "job_id": "job-2"}

    # Must not raise.
    await validate_request(state)

    assert state.get("source_language") != "en"
    assert state.get("source_language_confirmation_required") is True
    assert state.get("source_language_detection_reason") == "detector_error"
    assert decide_after_validate(state) == "finalize"


# ── AC-3 regression: declared language present -> unchanged, no detector ─


@patch("app.services.language_detection.detect_language")
@patch("app.agents.graph.get_audit_service")
@patch("app.agents.graph.get_db_service")
async def test_declared_language_on_state_bypasses_detection(
    mock_db_svc: MagicMock,
    mock_audit_svc: MagicMock,
    mock_detect: MagicMock,
) -> None:
    mock_db_svc.return_value = _make_db_mock(doc_meta={}, segments=[])
    mock_audit_svc.return_value = _make_audit_mock()

    from app.agents.graph import decide_after_validate, validate_request

    state = {
        "doc_id": "doc-3", "target_language": "es", "job_id": "job-3",
        "source_language": "fr",  # already resolved, e.g. via the API
    }
    await validate_request(state)

    assert state["source_language"] == "fr"
    assert not state.get("source_language_confirmation_required")
    mock_detect.assert_not_called()
    assert decide_after_validate(state) == "load_segments"


@patch("app.services.language_detection.detect_language")
@patch("app.agents.graph.get_audit_service")
@patch("app.agents.graph.get_db_service")
async def test_declared_language_in_doc_metadata_bypasses_detection(
    mock_db_svc: MagicMock,
    mock_audit_svc: MagicMock,
    mock_detect: MagicMock,
) -> None:
    mock_db_svc.return_value = _make_db_mock(doc_meta={"source_language": "de"}, segments=[])
    mock_audit_svc.return_value = _make_audit_mock()

    from app.agents.graph import decide_after_validate, validate_request

    state = {"doc_id": "doc-4", "target_language": "es", "job_id": "job-4"}
    await validate_request(state)

    assert state["source_language"] == "de"
    assert not state.get("source_language_confirmation_required")
    mock_detect.assert_not_called()
    assert decide_after_validate(state) == "load_segments"


# ── finalize_job: the held document lands on IN_REVIEW, not TRANSLATED ──


@pytest.mark.asyncio
@patch("app.agents.graph._emit_v2_audit_event")
@patch("app.agents.graph.get_audit_service")
@patch("app.agents.graph.get_db_service")
async def test_finalize_holds_job_on_language_confirmation_required(
    mock_db_svc: MagicMock,
    mock_audit_svc: MagicMock,
    mock_v2_emit: MagicMock,
) -> None:
    mock_db = MagicMock()
    mock_db_svc.return_value = mock_db
    mock_audit = MagicMock()
    mock_audit_svc.return_value = mock_audit

    from app.agents.graph import finalize_job
    from app.models.database import DocumentStatus

    state = {
        "doc_id": "doc-1",
        "job_id": "job-1",
        "audit_id": "audit-1",
        "quality_report": {},  # translate/gates never ran
        "segments": [],
        "source_language_confirmation_required": True,
        "source_language_detection_confidence": 0.31,
        "source_language_detection_reason": "low_confidence",
    }
    await finalize_job(state)

    mock_db.update_document_status.assert_called_once_with("doc-1", DocumentStatus.IN_REVIEW.value)

    payload = [c for c in mock_audit.log_event.call_args_list if c.args[1] == "JOB_FINALIZED"][0].args[2]
    assert payload["decision"] == "HELD"
    assert payload["source_language_confirmation_required"] is True
    assert payload["source_language_detection_reason"] == "low_confidence"
