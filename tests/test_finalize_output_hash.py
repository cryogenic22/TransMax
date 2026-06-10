"""TMX-3213 — the JOB_FINALIZED audit event must anchor a real output hash.

Closes the CLAUDE.md known issue `app/agents/graph.py:615 — output_hash:
"placeholder_hash"`. The terminal audit event is the regulator's anchor to the
actual translated artefact (A1); a literal placeholder makes the chain's last
link non-evidential.

Verifies:
  - `_compute_output_hash` is a deterministic, order-stable, total sha256
  - `finalize_job` writes that real hash into BOTH the legacy `log_event` and
    the v2 chain emit
  - no `"placeholder_hash"` literal remains under `app/`
"""
from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.agents.graph import _compute_output_hash

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


# ── AC-1: pure helper ───────────────────────────────────────────────────


def test_output_hash_is_hex64_and_deterministic() -> None:
    segs = [
        {"order_index": 0, "segment_id": "s1", "translated_text": "Hola mundo"},
        {"order_index": 1, "segment_id": "s2", "translated_text": "Adiós"},
    ]
    h1 = _compute_output_hash(segs)
    h2 = _compute_output_hash(list(segs))
    assert _HEX64.match(h1), f"not a sha256 hex digest: {h1!r}"
    assert h1 == h2, "hash must be deterministic for identical output"


def test_output_hash_is_order_stable() -> None:
    a = [
        {"order_index": 0, "segment_id": "s1", "translated_text": "uno"},
        {"order_index": 1, "segment_id": "s2", "translated_text": "dos"},
    ]
    b = list(reversed(a))  # same content, list order flipped
    assert _compute_output_hash(a) == _compute_output_hash(b), (
        "hash must be stable under list re-ordering (sorted by order_index, id)"
    )


def test_output_hash_changes_with_content() -> None:
    base = [{"order_index": 0, "segment_id": "s1", "translated_text": "uno"}]
    tampered = [{"order_index": 0, "segment_id": "s1", "translated_text": "UNO"}]
    assert _compute_output_hash(base) != _compute_output_hash(tampered)


def test_output_hash_empty_is_total() -> None:
    # AC-4: zero-segment job hashes the empty canonical form, never raises.
    assert _HEX64.match(_compute_output_hash([]))


# ── AC-2: finalize_job emits the real hash on both sinks ────────────────


@pytest.mark.asyncio
@patch("app.agents.graph._emit_v2_audit_event")
@patch("app.agents.graph.get_audit_service")
@patch("app.agents.graph.get_db_service")
async def test_finalize_writes_real_output_hash(
    mock_db_svc: MagicMock,
    mock_audit_svc: MagicMock,
    mock_v2_emit: MagicMock,
) -> None:
    mock_db_svc.return_value = MagicMock()
    mock_audit = MagicMock()
    mock_audit_svc.return_value = mock_audit

    from app.agents.graph import finalize_job

    segments = [
        {"order_index": 0, "segment_id": "s1", "translated_text": "Hola"},
        {"order_index": 1, "segment_id": "s2", "translated_text": "Mundo"},
    ]
    state = {
        "doc_id": "doc-1",
        "job_id": "job-1",
        "audit_id": "audit-1",
        "quality_report": {"status": "PASS"},
        "segments": segments,
    }
    await finalize_job(state)

    expected = _compute_output_hash(segments)

    # legacy log_event sink
    finalized = [c for c in mock_audit.log_event.call_args_list if c.args[1] == "JOB_FINALIZED"]
    assert len(finalized) == 1, f"expected one JOB_FINALIZED, got {len(finalized)}"
    payload = finalized[0].args[2]
    assert payload["output_hash"] == expected
    # A 64-hex sha256 (asserted below) cannot be the old "placeholder" literal;
    # the static guard test enforces its absence under app/ separately.
    assert _HEX64.match(payload["output_hash"])

    # v2 chain sink carries the same real hash
    assert mock_v2_emit.called, "finalize must also emit to the v2 chain"
    v2_payload = mock_v2_emit.call_args.kwargs["payload"]
    assert v2_payload["output_hash"] == expected


# ── AC-3: static guard ──────────────────────────────────────────────────


def test_no_placeholder_hash_literal_under_app() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    offenders: list[str] = []
    for py in (repo_root / "app").rglob("*.py"):
        if "placeholder_hash" in py.read_text(encoding="utf-8", errors="replace"):
            offenders.append(str(py.relative_to(repo_root)))
    assert not offenders, "placeholder_hash literal still present: " + ", ".join(offenders)
