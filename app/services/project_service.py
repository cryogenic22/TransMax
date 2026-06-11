"""
TMX-PROJECTS — project grouping for the translation job lifecycle.

A Project groups related documents (a regulatory submission, a study, a client
engagement) so the workspace can track a body of work above the single-document
level. All access is tenant-scoped: the caller MUST have an active
``org_context`` (set by the API tenant middleware or a test). The
``TenantScopedMixin`` auto-injects ``organization_id`` on insert and auto-filters
every SELECT, so this module never has to thread the org id through by hand.

Soft-delete (A9): removing a document from a project soft-deletes the join row;
archiving a project flips ``status`` rather than deleting it.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.database import Document, Project, ProjectDocument

logger = logging.getLogger(__name__)

PROJECT_STATUSES = ("active", "on_hold", "completed", "archived")


def create_project(
    db: Session,
    *,
    name: str,
    description: Optional[str] = None,
    client_name: Optional[str] = None,
    source_language: Optional[str] = None,
    target_languages: Optional[List[str]] = None,
    created_by: Optional[str] = None,
) -> Project:
    """Create a project in the current tenant. Fails loud on an empty name."""
    if not name or not name.strip():
        raise ValueError("project name is required")
    project = Project(
        name=name.strip(),
        description=description,
        client_name=client_name,
        status="active",
        source_language=source_language,
        target_languages=target_languages or [],
        created_by=created_by,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get_project(db: Session, project_id: str) -> Optional[Project]:
    return db.query(Project).filter(Project.id == project_id).first()


def list_projects(db: Session, *, status: Optional[str] = None) -> List[Project]:
    q = db.query(Project)
    if status:
        q = q.filter(Project.status == status)
    return q.order_by(Project.created_at.desc()).all()


def update_project(db: Session, project_id: str, **fields: object) -> Optional[Project]:
    """Patch mutable fields. Validates ``status`` against the allowed set (A3)."""
    project = get_project(db, project_id)
    if project is None:
        return None
    allowed = {
        "name",
        "description",
        "client_name",
        "status",
        "source_language",
        "target_languages",
    }
    if "status" in fields and fields["status"] not in PROJECT_STATUSES:
        raise ValueError(f"invalid status {fields['status']!r}")
    for key, value in fields.items():
        if key in allowed and value is not None:
            setattr(project, key, value)
    db.commit()
    db.refresh(project)
    return project


def add_document_to_project(
    db: Session, project_id: str, document_id: str, *, added_by: Optional[str] = None
) -> ProjectDocument:
    """Bind a document to a project. Idempotent; fails loud if either side is
    missing in this tenant (A3 — never silently group a non-existent doc)."""
    project = get_project(db, project_id)
    if project is None:
        raise ValueError(f"project {project_id} not found")
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise ValueError(f"document {document_id} not found")

    existing = (
        db.query(ProjectDocument)
        .filter(
            ProjectDocument.project_id == project_id,
            ProjectDocument.document_id == document_id,
        )
        .first()
    )
    if existing is not None:
        return existing

    membership = ProjectDocument(
        project_id=project_id, document_id=document_id, added_by=added_by
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


def remove_document_from_project(
    db: Session, project_id: str, document_id: str
) -> bool:
    """Soft-remove a document from a project. Returns True if a row was removed."""
    membership = (
        db.query(ProjectDocument)
        .filter(
            ProjectDocument.project_id == project_id,
            ProjectDocument.document_id == document_id,
        )
        .first()
    )
    if membership is None:
        return False
    # Soft-delete (A9): never DELETE; the auto-filter then hides this row while
    # leaving it recoverable, and a later re-add creates a fresh membership.
    membership.soft_delete()
    db.commit()
    return True


def count_project_documents(db: Session, project_id: str) -> int:
    """Number of documents currently grouped under a project (int, typed)."""
    return len(list_project_documents(db, project_id))


def list_project_documents(db: Session, project_id: str) -> List[Document]:
    """Return the Document rows bound to a project (active memberships only)."""
    doc_ids = [
        row.document_id
        for row in db.query(ProjectDocument)
        .filter(ProjectDocument.project_id == project_id)
        .all()
    ]
    if not doc_ids:
        return []
    return db.query(Document).filter(Document.id.in_(doc_ids)).all()


def project_summary(db: Session, project_id: str) -> Dict[str, object]:
    """Aggregate document counts by status for a project dashboard card."""
    documents = list_project_documents(db, project_id)
    by_status: Dict[str, int] = {}
    for doc in documents:
        by_status[doc.status] = by_status.get(doc.status, 0) + 1
    return {
        "project_id": project_id,
        "document_count": len(documents),
        "by_status": by_status,
    }
