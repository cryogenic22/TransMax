"""
TMX-ORCH-CHECKPOINT (Loop A) — recover orphaned PROCESSING jobs.

A LangGraph job is tracked by ``Document.status`` (``job_id == doc_id``).
``validate_request`` sets ``processing``; the engine writes Segment rows
throughout the translate phase and flips the Document to a terminal status only
at the end (``finalize_job`` / the engine's ``_update_document_status``). If the
worker dies before that terminal flip (deploy / OOM / kill), the doc is orphaned
in ``processing`` forever — invisible and never recovered.

This sweeper finds those orphans and flips them to ``IN_REVIEW`` (fail-toward
human triage, A3) with a ``JOB_SWEPT_STUCK`` audit event (A1). It is the
crash-recovery half of the ticket; a LangGraph checkpointer (resume) is Loop B.

Staleness anchor (the careful bit): ``Document.updated_at`` is NOT a liveness
signal — the engine does not heartbeat the Document row during translate, only
Segment rows. So "stuck" requires NO recent activity on the Document **or any of
its Segments** within the timeout — a live-but-slow job is actively writing
Segments and is therefore never swept.

Audit ordering: the ``JOB_SWEPT_STUCK`` event is emitted BEFORE the status flip
(A1 — audit precedes the side effect). The v2 emit shares the same v2 chain +
``translation_jobs`` FK behaviour as ``finalize_job``'s emit (system events are
v2-only since the v1 chain is being retired, TMX-3110d); it is fail-safe, so a
recovery is never blocked by an audit-sink hiccup (unblocking an orphan is the
safety priority — a swallowed-emit gap is logged loud, not silent).

Usage:
    python -m scripts.stuck_job_sweeper [--dry-run] [--json] [--timeout-seconds N]

Default-OFF: ``sweep()`` refuses to MUTATE unless ``stuck_job_sweep_enabled`` is
True (the gate lives in the mutation function, not just the CLI). ``--dry-run``
previews (read-only) regardless. Cross-tenant forensic read, then per-doc
``org_context`` for the write — mirrors ``scripts/mqm_shadow_report.py``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)

JOB_SWEPT_STUCK = "JOB_SWEPT_STUCK"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalise a DB datetime (often naive UTC on SQLite) to aware UTC so it can
    be compared against an aware cutoff without a TypeError."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def collect_stuck_docs(
    timeout_seconds: int,
    *,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Documents stuck in ``processing`` with NO activity (Document row OR any of
    its Segments) within the timeout. Cross-tenant forensic read
    (``include_other_tenants=True``). The activity filter is applied in Python so
    it is SQLite/Postgres-safe (the ``processing`` set is tiny).

    Anchoring on Document.updated_at ALONE would wrongly sweep a long-but-alive
    job: the engine writes Segment rows during translate but does not touch the
    Document row until the terminal flip, so Document.updated_at is frozen while
    the job is alive. Using the most recent Segment write as well makes the
    liveness signal sound.
    """
    from sqlalchemy import func

    from app.core.database import SessionLocal
    from app.models.database import Document, DocumentStatus, Segment

    cutoff = (now or _utcnow()) - timedelta(seconds=timeout_seconds)
    session = SessionLocal()
    try:
        rows = (
            session.query(Document)
            .filter(Document.status == DocumentStatus.PROCESSING.value)
            .execution_options(include_other_tenants=True)
            .all()
        )
        stuck: List[Dict[str, Any]] = []
        for d in rows:
            doc_ua = _as_utc(d.updated_at)
            seg_ua = _as_utc(
                session.query(func.max(Segment.updated_at))
                .filter(Segment.document_id == d.id)
                .execution_options(include_other_tenants=True)
                .scalar()
            )
            activity = [t for t in (doc_ua, seg_ua) if t is not None]
            last_activity = max(activity) if activity else None
            if last_activity is None or last_activity < cutoff:
                stuck.append(
                    {
                        "doc_id": d.id,
                        "organization_id": str(d.organization_id),
                        "last_activity": last_activity.isoformat()
                        if last_activity
                        else None,
                    }
                )
        return stuck
    finally:
        session.close()


def _emit_swept_audit(
    *, doc_id: str, timeout_seconds: int, last_activity: Optional[str]
) -> None:
    """Record the recovery on the canonical v2 audit chain (system actor, A1).

    Emitted BEFORE the status flip (audit-before-side-effect). Fail-safe inside
    ``emit_v2_audit_event``: a sink hiccup (e.g. a doc with no ``translation_jobs``
    row, same FK surface as ``finalize_job``'s v2 emit) is logged-not-raised so a
    recovery is never blocked — the priority is unblocking the orphan."""
    from app.agents._audit_v2_emit import emit_v2_audit_event

    emit_v2_audit_event(
        job_id=doc_id,
        event_type=JOB_SWEPT_STUCK,
        actor_id=None,
        actor_kind="system",
        payload={
            "_actor_node": "stuck_job_sweeper",
            "reason": "stuck_processing_timeout",
            "timeout_seconds": timeout_seconds,
            "last_activity": last_activity,
            "swept_at": _utcnow().isoformat(),
        },
    )


def _sweep_one(
    doc_id: str, org_id: str, timeout_seconds: int, last_activity: Optional[str]
) -> None:
    from app.core.tenant_context import org_context
    from app.models.database import DocumentStatus
    from app.services.db_service import get_db_service

    with org_context(org_id):
        # A1: audit precedes the side effect.
        _emit_swept_audit(
            doc_id=doc_id, timeout_seconds=timeout_seconds, last_activity=last_activity
        )
        get_db_service().update_document_status(doc_id, DocumentStatus.IN_REVIEW.value)


def sweep(
    timeout_seconds: int,
    *,
    dry_run: bool = False,
    enabled: Optional[bool] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Flip every stuck ``processing`` doc to ``IN_REVIEW`` with an audit event.

    Default-OFF mutation gate lives HERE (not just in the CLI): with
    ``enabled`` False (resolved from ``stuck_job_sweep_enabled`` when None), no
    doc is mutated regardless of caller — a future orchestrator importing
    ``sweep`` cannot bypass the flag. ``dry_run`` previews (read-only) regardless.
    Idempotent (the flip removes the doc from the ``processing`` set). One bad doc
    cannot abort the batch — per-doc errors are isolated and reported (A3)."""
    if enabled is None:
        enabled = bool(getattr(get_settings(), "stuck_job_sweep_enabled", False))
    will_mutate = enabled and not dry_run

    stuck = collect_stuck_docs(timeout_seconds, now=now)
    swept: List[str] = []
    errors: List[Dict[str, str]] = []
    for s in stuck:
        if not will_mutate:
            continue
        try:
            _sweep_one(
                s["doc_id"], s["organization_id"], timeout_seconds, s["last_activity"]
            )
            swept.append(s["doc_id"])
        except Exception as e:  # noqa: BLE001 — isolate: one orphan must not block the rest
            logger.warning("stuck-job sweep failed for doc %s: %s", s["doc_id"], e)
            errors.append({"doc_id": s["doc_id"], "error": str(e)})

    return {
        "timeout_seconds": timeout_seconds,
        "enabled": enabled,
        "dry_run": dry_run,
        "mutated": will_mutate,
        "candidates": len(stuck),
        "swept": swept,
        "swept_count": len(swept),
        "errors": errors,
        "candidate_docs": stuck if not will_mutate else None,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="stuck_job_sweeper", description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="preview candidates; write nothing"
    )
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=None,
        help="override the configured timeout",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    timeout = args.timeout_seconds or getattr(
        settings, "stuck_job_timeout_seconds", 1200
    )
    report = sweep(timeout, dry_run=args.dry_run)

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    if not report["mutated"] and not args.dry_run:
        print(
            f"Stuck-job sweeper SKIPPED — stuck_job_sweep_enabled is False (candidates={report['candidates']}; --dry-run to preview)"
        )
        return 0
    mode = "DRY-RUN (no writes)" if args.dry_run else "SWEEP"
    print(f"Stuck-job sweeper [{mode}] timeout={timeout}s")
    print("-" * 60)
    print(f"  candidates : {report['candidates']}")
    if not report["mutated"]:
        for d in report.get("candidate_docs") or []:
            print(f"    would-sweep {d['doc_id']} (last_activity={d['last_activity']})")
    else:
        print(f"  swept      : {report['swept_count']} -> IN_REVIEW")
        if report["errors"]:
            print(f"  errors     : {len(report['errors'])} (isolated; see logs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
