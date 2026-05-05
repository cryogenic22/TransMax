"""
TMX-3212 — Audit timestamp fix.

Regression guard for the defect closed at app/agents/graph.py:149 and :438, where
audit-event timestamps were computed via
    logging.Formatter.formatTime(logging.Formatter(), logging.LogRecord("",0,"","",None,None,None))
which always returned the same meaningless `time.localtime(0)`-derived string.

The fix replaces both call sites with `datetime.now(timezone.utc).isoformat()`.

These tests verify:
  - JOB_STARTED audit-event payloads carry a parseable ISO-8601 UTC timestamp
  - Two events emitted in sequence produce monotonically non-decreasing timestamps
  - run_quality_gates appends scorecard_history entries with parseable ISO-8601 UTC timestamps
  - There are no remaining `Formatter.formatTime` calls anywhere under app/

If any of these regress, audit chain timestamps are no longer defensible — see CLAUDE.md A1.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── ISO-8601 UTC parsing helpers ────────────────────────────────────────


def _assert_iso8601_utc(timestamp: str) -> datetime:
    """Parse `timestamp` as ISO-8601, assert tz-aware UTC, return parsed datetime."""
    parsed = datetime.fromisoformat(timestamp)
    assert parsed.tzinfo is not None, (
        f"Audit timestamp {timestamp!r} is timezone-naive — must be UTC-aware "
        "(see CLAUDE.md A1 + EU AI Act technical-documentation requirement)."
    )
    offset = parsed.utcoffset()
    assert offset is not None and offset.total_seconds() == 0, (
        f"Audit timestamp {timestamp!r} is not UTC (offset={offset})."
    )
    return parsed


# ── Tests on validate_request (line 149) ────────────────────────────────


@patch("app.agents.graph.get_audit_service")
@patch("app.agents.graph.get_db_service")
async def test_validate_request_emits_iso8601_utc_timestamp(
    mock_db_svc: MagicMock,
    mock_audit_svc: MagicMock,
) -> None:
    mock_db = MagicMock()
    mock_db.get_document_status.return_value = "PENDING"
    mock_db_svc.return_value = mock_db

    mock_audit = MagicMock()
    mock_audit.create_audit_trail.return_value = "audit-xyz"
    mock_audit_svc.return_value = mock_audit

    from app.agents.graph import validate_request

    state = {
        "doc_id": "doc-1",
        "target_language": "es",
        "source_language": "en",  # pre-set to skip language detection
        "job_id": "job-1",
    }
    await validate_request(state)

    job_started_calls = [
        c for c in mock_audit.log_event.call_args_list if c.args[1] == "JOB_STARTED"
    ]
    assert len(job_started_calls) == 1, (
        f"Expected exactly one JOB_STARTED event, got {len(job_started_calls)}"
    )
    payload = job_started_calls[0].args[2]
    assert "timestamp" in payload, "JOB_STARTED payload missing 'timestamp' field"
    _assert_iso8601_utc(payload["timestamp"])


@patch("app.agents.graph.get_audit_service")
@patch("app.agents.graph.get_db_service")
async def test_two_validate_requests_produce_monotonic_timestamps(
    mock_db_svc: MagicMock,
    mock_audit_svc: MagicMock,
) -> None:
    mock_db = MagicMock()
    mock_db.get_document_status.return_value = "PENDING"
    mock_db_svc.return_value = mock_db

    mock_audit = MagicMock()
    mock_audit.create_audit_trail.return_value = "audit-xyz"
    mock_audit_svc.return_value = mock_audit

    from app.agents.graph import validate_request

    state1 = {"doc_id": "d1", "target_language": "es", "source_language": "en", "job_id": "j1"}
    state2 = {"doc_id": "d2", "target_language": "es", "source_language": "en", "job_id": "j2"}

    await validate_request(state1)
    # Tiny sleep so monotonic is observable even on coarse clocks.
    await asyncio.sleep(0.001)
    await validate_request(state2)

    timestamps = [
        _assert_iso8601_utc(c.args[2]["timestamp"])
        for c in mock_audit.log_event.call_args_list
        if c.args[1] == "JOB_STARTED"
    ]
    assert len(timestamps) == 2, f"Expected two JOB_STARTED events, got {len(timestamps)}"
    assert timestamps[0] <= timestamps[1], (
        f"Timestamps must be monotonic non-decreasing: {timestamps[0]} > {timestamps[1]}"
    )


# ── Test on run_quality_gates (line 439) ────────────────────────────────


@patch("app.agents.graph.get_audit_service")
@patch("app.agents.graph.get_db_service")
@patch("app.agents.graph.get_quality_gate_service")
async def test_run_quality_gates_appends_iso8601_utc_to_scorecard_history(
    mock_qg_svc: MagicMock,
    mock_db_svc: MagicMock,
    mock_audit_svc: MagicMock,
) -> None:
    # No segments → skip the per-segment loop; we only need verdict + history.
    mock_qg = MagicMock()
    mock_qg.evaluate_verdict.return_value = {
        "status": "PASS",
        "metrics": {"pass_rate": 100, "drift_score": 0},
        "reason": "ok",
    }
    mock_qg_svc.return_value = mock_qg

    mock_audit_svc.return_value = MagicMock()
    mock_db_svc.return_value = MagicMock()

    from app.agents.graph import run_quality_gates

    state = {
        "segments": [],  # skip per-segment processing
        "constraint_pack": {},
        "target_language": "es",
        "source_language": "en",
        "audit_id": "audit-xyz",
    }
    await run_quality_gates(state)

    history = state.get("scorecard_history")
    assert history is not None and len(history) == 1, (
        f"Expected exactly one scorecard_history entry, got {history!r}"
    )
    entry = history[0]
    assert "timestamp" in entry, "scorecard_history entry missing 'timestamp'"
    _assert_iso8601_utc(entry["timestamp"])


# ── Static regression guard — no Formatter.formatTime under app/ ────────


def test_no_formatter_formattime_calls_in_app() -> None:
    """
    AC-6 — no remaining `Formatter.formatTime` calls anywhere under app/.

    This is a static regression guard. If a future refactor reintroduces the
    pattern, this test fails fast — pre-commit, before any audit event ships
    a meaningless timestamp into a regulator-facing record (CLAUDE.md A1).
    """
    repo_root = Path(__file__).resolve().parent.parent
    app_dir = repo_root / "app"

    offenders: list[str] = []
    for py in app_dir.rglob("*.py"):
        text = py.read_text(encoding="utf-8", errors="replace")
        if "Formatter.formatTime" in text:
            offenders.append(str(py.relative_to(repo_root)))

    assert not offenders, (
        "Files still contain Formatter.formatTime — replace with "
        "datetime.now(timezone.utc).isoformat() per TMX-3212. Offenders: " + ", ".join(offenders)
    )
