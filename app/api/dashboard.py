"""
Dashboard API — provides real-time KPI stats and recent activity
for the Control Tower dashboard.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta

from app.core.database import get_db
from app.models.database import Document, Segment

router = APIRouter()


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
