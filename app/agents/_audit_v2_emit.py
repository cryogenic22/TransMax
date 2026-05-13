"""
TMX-3110 Phase 1 — v2 audit emit shim for the LangGraph pipeline.

This module is a thin adapter that lets the LangGraph nodes in
`app/agents/graph.py` double-write to the v2 audit chain alongside the
v1 chain (`app/services/audit_service.py`). It exists so the graph
module doesn't grow past the 800-line ratchet threshold and so the
Phase 1 contract is isolated in one place — making the Phase 4 removal
(TMX-3110d) a one-file delete.

Contract
--------

`emit_v2_audit_event` is the ONLY entry point. It accepts the same
kw-only arguments as `AuditWriterV2.record_event`. If the v2 write
fails, it logs at WARNING with structured context and returns; it does
NOT raise. This is the documented exception to A3 (no silent fallbacks)
for Phase 1: v2 failures must NOT propagate to v1's caller because the
contract is "v2 chain catches up WITHOUT changing v1's behaviour".

The TMX-3104 verifier independently detects any missing-event sequence
gap, so the gap surfaces via the canonical defence-of-evidence
mechanism — not silently swallowed.

This wrapper has an explicit end-of-life: Phase 4 (TMX-3110d) inverts
responsibility — v2 becomes mandatory, v1 becomes optional, and this
broad-except moves to v1's emit. At that point this module is deleted.

Addenda
-------
* **A1** — increases audit coverage; v2 chain catches up.
* **A3** — broad-except is a CONTROLLED fallback with documented EOL,
  not a silent fallback; failure surfaced via WARNING + verifier.
* **A6** — payload-shape-agnostic; callers pass the same payload as v1.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.services.audit_writer_v2 import ActorKind, AuditWriterV2

logger = logging.getLogger(__name__)

_audit_writer_v2: Optional[AuditWriterV2] = None


def _get_audit_writer_v2() -> AuditWriterV2:
    """Lazy singleton for the v2 audit writer.

    The session factory is a thunk that reads `app.core.database.SessionLocal`
    at call time, so the `fresh_engine_for_db` test fixture (which swaps
    `SessionLocal` in place) is picked up correctly across tests.
    """
    global _audit_writer_v2
    if _audit_writer_v2 is None:
        def _session_factory():
            from app.core.database import SessionLocal as _SL
            return _SL()
        _audit_writer_v2 = AuditWriterV2(session_factory=_session_factory)
    return _audit_writer_v2


def reset_writer_singleton_for_test() -> None:
    """Test-only: clear the writer singleton so the next call rebuilds it.

    Required when the test fixture swaps the underlying engine; without
    this reset the singleton would carry a stale session factory closure.
    """
    global _audit_writer_v2
    _audit_writer_v2 = None


def emit_v2_audit_event(
    *,
    job_id: str,
    event_type: str,
    actor_id: Optional[str],
    actor_kind: ActorKind,
    payload: dict[str, Any],
) -> None:
    """TMX-3110 Phase 1: emit one v2 audit event alongside the v1 path.

    See module docstring for the A3 / broad-except justification and the
    Phase 4 / TMX-3110d removal plan.
    """
    try:
        # Phase 1 double-write: v2 failures are logged but don't block v1 — see TMX-3110 worksheet stage 3
        _get_audit_writer_v2().record_event(
            job_id=job_id,
            event_type=event_type,
            actor_id=actor_id,
            actor_kind=actor_kind,
            payload=payload,
        )
    except Exception as exc:  # noqa: BLE001 — intentional; see module docstring; removed in TMX-3110d
        logger.warning(
            "v2 audit emit failed (event_type=%s, job_id=%s, reason=%s) — "
            "v1 chain unaffected, v2 chain has gap (TMX-3104 verifier will report)",
            event_type, job_id, exc,
        )
