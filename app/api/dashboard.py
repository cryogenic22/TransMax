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
    A future ticket (TMX-3603-richtarget) will resolve `audit_id` →
    document name through TranslationJobQueue.request_json; for now the
    target falls back to `audit <8-char>` so the feed shape is stable.
    """
    cap = max(1, min(limit, 100))
    entries = (
        db.query(AuditLogEntry)
        .order_by(AuditLogEntry.timestamp.desc())
        .limit(cap)
        .all()
    )

    items = [_map_log_entry_to_activity_event(e, None) for e in entries]
    return {"items": items, "total": len(items)}


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

    activities: list[dict[str, Any]] = []
    for e in entries:
        agent_meta = _EVENT_TYPE_TO_AGENT.get(e.event_type or "", {"id": "system"})
        agent = agent_meta["id"]
        # The AgentLanes component only accepts the four canonical agents;
        # synthetic / system events are skipped for the lane view.
        if agent not in {"translator", "reviewer", "fixer", "auditor"}:
            continue
        activities.append({
            "id": str(e.entry_id),
            "agent": agent,
            "label": _EVENT_TYPE_TO_ACTION.get(e.event_type or "", e.event_type or "step"),
            "startedAt": e.timestamp.isoformat() if e.timestamp else None,
            "status": "complete",   # AuditLogEntry rows are always post-hoc; no in-flight state in this table
        })
    return {"activities": activities}


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
