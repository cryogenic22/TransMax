"""TMX-FEEDBACK-1 — in-app user feedback API.

Captures bug reports, issues, enhancements, feature requests, and data
feedback submitted from the UI. The Phase-3 automation (`/triage-feedback`,
`/process-feedback`, `/feedback-cron`) polls `GET /api/feedback?status=new`,
classifies each row, and transitions it via `PATCH`.

Conventions:
  - tenant-scoped (TMX-3011/3012): `organization_id` auto-injects from the
    request tenant context; reads auto-filter to the caller's org.
  - soft-delete only (A9): DELETE marks `is_deleted`; never hard-deletes.
  - auth-adaptive (AC-6): all endpoints depend on `get_current_user`, which
    returns a dev identity in AUTH_MODE=none and a real user once
    TMX-AUTH-WALL flips AUTH_MODE=jwt.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.providers import AuthenticatedIdentity
from app.core.database import get_db
from app.models.database import Feedback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/feedback", tags=["Feedback"])

VALID_CATEGORIES = {
    "bug",
    "issue",
    "enhancement",
    "feature",
    "data_quality",
    "data_request",
}
VALID_PRIORITIES = {"low", "medium", "high", "critical"}
VALID_STATUSES = {"new", "triaged", "in_progress", "resolved", "rejected"}


class FeedbackCreateRequest(BaseModel):
    category: str
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    session_id: Optional[str] = None
    page_url: Optional[str] = None
    entity_context: Optional[dict] = None
    diagnostic_context: Optional[dict] = None
    attachments: Optional[list] = None


class FeedbackUpdateRequest(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    resolution: Optional[str] = None
    resolved_by: Optional[str] = None


def _to_dict(fb: Feedback) -> dict:
    return {
        "id": fb.id,
        "user_id": fb.user_id,
        "page_url": fb.page_url,
        "category": fb.category,
        "title": fb.title,
        "description": fb.description,
        "priority": fb.priority,
        "status": fb.status,
        "resolution": fb.resolution,
        "resolved_by": fb.resolved_by,
        "entity_context": fb.entity_context,
        "diagnostic_context": fb.diagnostic_context,
        "attachments": fb.attachments,
        "created_at": fb.created_at.isoformat() if fb.created_at else None,
        "updated_at": fb.updated_at.isoformat() if fb.updated_at else None,
    }


@router.post("")
def create_feedback(
    body: FeedbackCreateRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(get_current_user),
):
    """Create a feedback entry (status='new'). org_id auto-injects from context."""
    if body.category not in VALID_CATEGORIES:
        raise HTTPException(
            400,
            f"Invalid category: {body.category}. Must be one of {sorted(VALID_CATEGORIES)}",
        )
    if body.priority not in VALID_PRIORITIES:
        raise HTTPException(
            400,
            f"Invalid priority: {body.priority}. Must be one of {sorted(VALID_PRIORITIES)}",
        )

    fb = Feedback(
        user_id=user.user_id,
        session_id=body.session_id,
        page_url=body.page_url,
        category=body.category,
        title=body.title,
        description=body.description,
        priority=body.priority,
        status="new",
        entity_context=body.entity_context,
        diagnostic_context=body.diagnostic_context,
        attachments=body.attachments or [],
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    logger.info("Feedback created: %s (%s) — %s", fb.id, fb.category, fb.title)
    return {
        "feedback": {
            "id": fb.id,
            "category": fb.category,
            "title": fb.title,
            "status": fb.status,
            "priority": fb.priority,
            "created_at": fb.created_at.isoformat() if fb.created_at else None,
        }
    }


@router.get("")
def list_feedback(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(get_current_user),
):
    """List feedback (tenant + non-deleted auto-filtered), newest first."""
    q = db.query(Feedback)
    if status:
        if status not in VALID_STATUSES:
            raise HTTPException(400, f"Invalid status: {status}")
        q = q.filter(Feedback.status == status)
    if category:
        if category not in VALID_CATEGORIES:
            raise HTTPException(400, f"Invalid category: {category}")
        q = q.filter(Feedback.category == category)

    total = q.count()
    rows = q.order_by(Feedback.created_at.desc()).limit(limit).offset(offset).all()
    return {
        "items": [_to_dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/stats")
def feedback_stats(
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(get_current_user),
):
    """Aggregate counts by category and status for the caller's org."""
    rows = db.query(Feedback).all()
    by_category: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for r in rows:
        by_category[r.category] = by_category.get(r.category, 0) + 1
        by_status[r.status] = by_status.get(r.status, 0) + 1
    return {"total": len(rows), "by_category": by_category, "by_status": by_status}


@router.patch("/{feedback_id}")
def update_feedback(
    feedback_id: str,
    body: FeedbackUpdateRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(get_current_user),
):
    """Update status / priority / resolution / resolved_by. Used by the automation."""
    if body.status is not None and body.status not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status: {body.status}")
    if body.priority is not None and body.priority not in VALID_PRIORITIES:
        raise HTTPException(400, f"Invalid priority: {body.priority}")

    fb = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if not fb:
        raise HTTPException(404, f"Feedback {feedback_id} not found")

    if body.status is not None:
        fb.status = body.status
    if body.priority is not None:
        fb.priority = body.priority
    if body.resolution is not None:
        fb.resolution = body.resolution
    if body.resolved_by is not None:
        fb.resolved_by = body.resolved_by
    fb.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(fb)
    return {
        "feedback": {
            "id": fb.id,
            "status": fb.status,
            "priority": fb.priority,
            "resolution": fb.resolution,
            "resolved_by": fb.resolved_by,
            "updated_at": fb.updated_at.isoformat() if fb.updated_at else None,
        }
    }


@router.delete("/{feedback_id}", status_code=204)
def delete_feedback(
    feedback_id: str,
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(get_current_user),
):
    """Soft-delete (A9) — sets is_deleted; never hard-deletes."""
    fb = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if not fb:
        raise HTTPException(404, f"Feedback {feedback_id} not found")
    fb.soft_delete(actor_id=user.user_id)
    db.commit()
    logger.info("Feedback soft-deleted: %s by %s", feedback_id, user.user_id)
    return None
