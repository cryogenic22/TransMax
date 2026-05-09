"""
Dashboard API — provides real-time KPI stats and recent activity
for the Control Tower dashboard.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta
from typing import Any

from app.core.database import get_db
from app.models.database import Document, Segment
from app.models.models import AuditRecord, AuditLogEntry

router = APIRouter()


# ─── Activity Feed wire-shape (TMX-3603-wire) ────────────────────────────
#
# Maps AuditLogEntry rows → ActivityEvent shape consumed by the frontend
# `<ActivityFeed>` component. AuditLogEntry is the per-event log written
# by AuditService.log_event during translation jobs (audit_service.py:53).
# Mapping rules below — single source of truth so the contract test in
# tests/test_dashboard_activity_feed.py can pin it.

_EVENT_TYPE_TO_ACTION: dict[str, str] = {
    "JOB_STARTED":           "started",
    "TRANSLATION_GENERATED": "translated",
    "GATE_CHECK":            "ran quality gates on",
    "GATE_PASSED":           "passed quality gates on",
    "GATE_FAILED":           "flagged defects on",
    "REFINEMENT_LOOP":       "refined",
    "REVERSE_TRANSLATE":     "reverse-translated",
    "AUDIT_SEAL":            "sealed audit chain on",
    "JOB_COMPLETED":         "completed",
}

_EVENT_TYPE_TO_AGENT: dict[str, dict[str, str]] = {
    "JOB_STARTED":           {"id": "system",     "name": "Translation pipeline"},
    "TRANSLATION_GENERATED": {"id": "translator", "name": "Translator agent"},
    "GATE_CHECK":            {"id": "reviewer",   "name": "Reviewer agent"},
    "GATE_PASSED":           {"id": "reviewer",   "name": "Reviewer agent"},
    "GATE_FAILED":           {"id": "reviewer",   "name": "Reviewer agent"},
    "REFINEMENT_LOOP":       {"id": "fixer",      "name": "Fixer agent"},
    "REVERSE_TRANSLATE":     {"id": "reviewer",   "name": "Reviewer agent"},
    "AUDIT_SEAL":            {"id": "auditor",    "name": "Auditor agent"},
    "JOB_COMPLETED":         {"id": "system",     "name": "Translation pipeline"},
}


def _map_log_entry_to_activity_event(entry: AuditLogEntry, target_label: str | None) -> dict[str, Any]:
    """Translate one AuditLogEntry into the ActivityEvent wire shape."""
    event_type = entry.event_type or "UNKNOWN"
    actor = _EVENT_TYPE_TO_AGENT.get(event_type, {"id": "system", "name": "System"})
    actor_type = "agent" if actor["id"] in {"translator", "reviewer", "fixer", "auditor"} else "system"
    action = _EVENT_TYPE_TO_ACTION.get(event_type, event_type.lower().replace("_", " "))
    target = target_label or f"audit {entry.audit_id[:8] if entry.audit_id else '—'}"
    return {
        "id": str(entry.entry_id),
        "actor": {"type": actor_type, "id": actor["id"], "name": actor["name"]},
        "action": action,
        "target": target,
        "occurredAt": entry.timestamp.isoformat() if entry.timestamp else None,
    }


def _resolve_audit_id_to_doc_name(
    db: Session,
    audit_ids: set[str],
) -> dict[str, str]:
    """
    Resolve a set of audit_ids to human-readable document names.

    Mechanism (TMX-3603-wire-deeper):
      1. Each audit chain's JOB_STARTED log entry carries the doc_id in
         its payload — the LangGraph writes it there at chain creation
         (app/agents/graph.py:151).
      2. We pull every JOB_STARTED entry for the requested audit_ids in
         a single query, then look up the Document.name for each doc_id.
      3. Returns { audit_id: doc_name }. audit_ids with no JOB_STARTED
         entry, or a JOB_STARTED entry that lacks a doc_id, or a doc_id
         that doesn't resolve to a Document, are absent from the map —
         the caller falls back to its short-id format.

    Two queries total regardless of input size (no N+1).
    """
    if not audit_ids:
        return {}
    starts = (
        db.query(AuditLogEntry)
        .filter(
            AuditLogEntry.audit_id.in_(audit_ids),
            AuditLogEntry.event_type == "JOB_STARTED",
        )
        .all()
    )
    audit_to_doc_id: dict[str, str] = {}
    for s in starts:
        payload = s.payload or {}
        doc_id = payload.get("doc_id") if isinstance(payload, dict) else None
        if isinstance(doc_id, str) and s.audit_id:
            audit_to_doc_id[s.audit_id] = doc_id
    if not audit_to_doc_id:
        return {}
    rows = (
        db.query(Document.id, Document.name)
        .filter(Document.id.in_(set(audit_to_doc_id.values())))
        .all()
    )
    doc_name_by_id: dict[str, str] = {row[0]: row[1] for row in rows}
    return {
        audit_id: doc_name_by_id[doc_id]
        for audit_id, doc_id in audit_to_doc_id.items()
        if doc_id in doc_name_by_id
    }


@router.get("/activity-feed")
def get_activity_feed(
    limit: int = 25,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return the recent platform activity stream in the wire shape consumed
    by the frontend `<ActivityFeed>` component (TMX-3603-wire).

    Source: `audit_log_entries` rows ordered by timestamp DESC. Each entry
    is the per-event tamper-evident log written by AuditService.log_event.
    Audit chains are resolved to human-readable document names via
    `_resolve_audit_id_to_doc_name` (TMX-3603-wire-deeper); chains with
    no resolvable doc fall back to the short audit-id format.
    """
    cap = max(1, min(limit, 100))
    entries = (
        db.query(AuditLogEntry)
        .order_by(AuditLogEntry.timestamp.desc())
        .limit(cap)
        .all()
    )

    audit_ids = {e.audit_id for e in entries if e.audit_id}
    doc_name_by_audit = _resolve_audit_id_to_doc_name(db, audit_ids)

    items = [
        _map_log_entry_to_activity_event(
            e,
            doc_name_by_audit.get(e.audit_id) if e.audit_id else None,
        )
        for e in entries
    ]
    return {"items": items, "total": len(items)}


def _audit_log_entries_to_agent_activities(entries: list[AuditLogEntry]) -> list[dict[str, Any]]:
    """Map AuditLogEntry rows -> AgentActivity wire shape, filtered to the
    four canonical agents only (system / synthetic events are skipped)."""
    activities: list[dict[str, Any]] = []
    for e in entries:
        agent_meta = _EVENT_TYPE_TO_AGENT.get(e.event_type or "", {"id": "system"})
        agent = agent_meta["id"]
        if agent not in {"translator", "reviewer", "fixer", "auditor"}:
            continue
        activities.append({
            "id": str(e.entry_id),
            "agent": agent,
            "label": _EVENT_TYPE_TO_ACTION.get(e.event_type or "", e.event_type or "step"),
            "startedAt": e.timestamp.isoformat() if e.timestamp else None,
            "status": "complete",
        })
    return activities


@router.get("/agent-activity/{audit_id}")
def get_agent_activity(audit_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Return per-agent activity for a single audit chain (= one job) in the
    wire shape consumed by `<AgentLanes>`. Each AuditLogEntry becomes one
    AgentActivity assigned to the agent its event_type maps to.
    """
    entries = (
        db.query(AuditLogEntry)
        .filter(AuditLogEntry.audit_id == audit_id)
        .order_by(AuditLogEntry.sequence_index.asc())
        .all()
    )

    return {"activities": _audit_log_entries_to_agent_activities(entries)}


@router.get("/agent-activity-by-job/{job_id}")
def get_agent_activity_by_job(job_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    TMX-3603-jobs-id companion endpoint. Looks up the AuditRecord for
    a job_id (typically the document id used by /workspace/jobs/[id]),
    then returns per-agent activity for the chain in the same wire shape
    as `/agent-activity/{audit_id}`.

    Behaviour when the job_id has no audit chain (e.g. a fresh upload
    that hasn't started translation yet) is empty `activities: []` —
    the consumer renders the empty-state lanes without conditional
    rendering.
    """
    record = (
        db.query(AuditRecord)
        .filter(AuditRecord.job_id == job_id)
        .order_by(AuditRecord.created_at.desc())
        .first()
    )
    if not record:
        return {"activities": [], "audit_id": None}

    entries = (
        db.query(AuditLogEntry)
        .filter(AuditLogEntry.audit_id == record.audit_id)
        .order_by(AuditLogEntry.sequence_index.asc())
        .all()
    )
    return {
        "activities": _audit_log_entries_to_agent_activities(entries),
        "audit_id": record.audit_id,
    }


@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Return KPI metrics for the Control Tower."""
    total_docs = db.query(func.count(Document.id)).scalar() or 0

    active_jobs = db.query(func.count(Document.id)).filter(
        Document.status.in_(["processing", "uploaded"])
    ).scalar() or 0

    # Average confidence across all scored documents
    avg_quality = db.query(func.avg(Document.confidence_score)).filter(
        Document.confidence_score.isnot(None)
    ).scalar()
    avg_quality_pct = round(avg_quality * 100, 1) if avg_quality else None

    # Completed in last 24h
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    completed_24h = db.query(func.count(Document.id)).filter(
        Document.status.in_(["translated", "approved"]),
        Document.updated_at >= cutoff,
    ).scalar() or 0

    # Total segments and translated segments (for velocity)
    total_segments = db.query(func.count(Segment.id)).scalar() or 0
    translated_segments = db.query(func.count(Segment.id)).filter(
        Segment.status.in_(["translated", "edited", "approved"])
    ).scalar() or 0

    return {
        "total_documents": total_docs,
        "active_jobs": active_jobs,
        "avg_quality_pct": avg_quality_pct,
        "completed_24h": completed_24h,
        "total_segments": total_segments,
        "translated_segments": translated_segments,
    }


@router.get("/activity")
def get_recent_activity(limit: int = 10, db: Session = Depends(get_db)):
    """Return recent document activity for the inbox/tasks panel."""
    # Recent documents requiring review or recently completed
    docs = (
        db.query(Document)
        .filter(Document.status.in_(["in_review", "translated", "processing"]))
        .order_by(Document.updated_at.desc())
        .limit(limit)
        .all()
    )

    items = []
    for doc in docs:
        # Determine priority based on status
        if doc.status == "in_review":
            priority = "High"
            desc = "Pending human review"
        elif doc.status == "processing":
            priority = "Medium"
            desc = "Translation in progress"
        else:
            priority = "Low"
            desc = "Translation complete"

        # Quality flag
        if doc.confidence_score and doc.confidence_score < 0.8:
            priority = "High"
            desc = f"Low quality score ({doc.confidence_score:.0%})"

        items.append({
            "id": doc.id,
            "title": doc.name,
            "desc": desc,
            "status": doc.status,
            "priority": priority,
            "target_language": doc.target_language,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        })

    return items
