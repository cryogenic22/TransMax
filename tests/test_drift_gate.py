"""TMX-DRIFT-GATE — back-translation drift becomes an enforced review gate.

Today `reverse_translate_node` measures per-segment back-translation fidelity
(`validation_score`, 0-100, 100=identical) but nothing acts on it, so a job
whose back-translation diverges badly still finalizes as TRANSLATED. This gate
holds such a job for a human (A2 deterministic gate, A3 fail-toward-review).

Verifies:
  - `assess_reflexion` only counts genuinely-assessed scores (excludes None and
    the 0.0 no-API-key sentinel) and flags review on any assessed score < 70
  - `finalize_job` escalates TRANSLATED -> IN_REVIEW when the flag is set, records
    the reason in the audit payload, and never downgrades an already-held status
  - no `print(` remains in the reflexion node (logger only)
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.agents.nodes.reverse_translate import REFLEXION_REVIEW_THRESHOLD, assess_reflexion


# ── AC-1/2: pure assessor ───────────────────────────────────────────────


def test_assess_flags_review_on_low_score() -> None:
    segs = [{"validation_score": 95.0}, {"validation_score": 42.0}, {"validation_score": 88.0}]
    out = assess_reflexion(segs)
    assert out["review_required"] is True
    assert out["min_score"] == 42.0
    assert out["n_assessed"] == 3
    assert out["n_below"] == 1


def test_assess_clean_job_not_held() -> None:
    segs = [{"validation_score": 95.0}, {"validation_score": 91.0}]
    out = assess_reflexion(segs)
    assert out["review_required"] is False
    assert out["min_score"] == 91.0


def test_assess_excludes_none_but_zero_gates() -> None:
    # Since TMX-DRIFT-SENTINEL, `None` is the sole "unavailable" sentinel and is
    # excluded; a real `0.0` is a catastrophic score that MUST gate.
    segs = [{"validation_score": 0.0}, {"validation_score": None}, {"foo": "bar"}]
    out = assess_reflexion(segs)
    assert out["review_required"] is True   # the genuine 0.0 holds the job
    assert out["n_assessed"] == 1           # only the 0.0 is a real signal
    assert out["min_score"] == 0.0


def test_assess_boundary_threshold_inclusive_pass() -> None:
    # exactly at threshold is NOT below -> not held
    segs = [{"validation_score": REFLEXION_REVIEW_THRESHOLD}]
    assert assess_reflexion(segs)["review_required"] is False


# ── AC-4: finalize_job escalation ───────────────────────────────────────


@pytest.mark.asyncio
@patch("app.agents.graph._emit_v2_audit_event")
@patch("app.agents.graph.get_audit_service")
@patch("app.agents.graph.get_db_service")
async def test_finalize_holds_job_on_drift(
    mock_db_svc: MagicMock,
    mock_audit_svc: MagicMock,
    mock_v2_emit: MagicMock,
) -> None:
    mock_db_svc.return_value = MagicMock()
    mock_audit = MagicMock()
    mock_audit_svc.return_value = mock_audit

    from app.agents.graph import finalize_job

    state = {
        "doc_id": "doc-1",
        "job_id": "job-1",
        "audit_id": "audit-1",
        "quality_report": {"status": "PASS"},  # deterministic gates passed
        "segments": [{"order_index": 0, "segment_id": "s1", "translated_text": "x"}],
        "reflexion_review_required": True,
        "reflexion_min_score": 42.0,
    }
    await finalize_job(state)

    payload = [c for c in mock_audit.log_event.call_args_list if c.args[1] == "JOB_FINALIZED"][0].args[2]
    # A PASS job with drift is HELD, not passed.
    assert payload["decision"] == "HELD"
    assert payload["reflexion_review_required"] is True
    assert payload["reflexion_min_score"] == 42.0


@pytest.mark.asyncio
@patch("app.agents.graph._emit_v2_audit_event")
@patch("app.agents.graph.get_audit_service")
@patch("app.agents.graph.get_db_service")
async def test_finalize_passes_clean_job(
    mock_db_svc: MagicMock,
    mock_audit_svc: MagicMock,
    mock_v2_emit: MagicMock,
) -> None:
    mock_db_svc.return_value = MagicMock()
    mock_audit = MagicMock()
    mock_audit_svc.return_value = mock_audit

    from app.agents.graph import finalize_job

    state = {
        "doc_id": "doc-1",
        "job_id": "job-1",
        "audit_id": "audit-1",
        "quality_report": {"status": "PASS"},
        "segments": [{"order_index": 0, "segment_id": "s1", "translated_text": "x"}],
        "reflexion_review_required": False,
    }
    await finalize_job(state)

    payload = [c for c in mock_audit.log_event.call_args_list if c.args[1] == "JOB_FINALIZED"][0].args[2]
    assert payload["decision"] == "PASS"
    assert "reflexion_review_required" not in payload


# ── AC-5: hygiene ───────────────────────────────────────────────────────


def test_no_print_in_reflexion_node() -> None:
    src = (
        Path(__file__).resolve().parent.parent
        / "app" / "agents" / "nodes" / "reverse_translate.py"
    ).read_text(encoding="utf-8")
    assert "print(" not in src, "reverse_translate.py must use logger, not print()"
