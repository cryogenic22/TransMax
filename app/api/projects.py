"""
TMX-PROJECTS — project API.

Groups translation jobs/documents into projects so the workspace can manage a
body of work (a submission, study, or client engagement) above the single-
document level. Backward-compatible, additive surface (A7 — lives under the
canonical /workspace data plane via /api/projects); no existing endpoint or
schema changes. Tenant context is set by TenantContextMiddleware; soft-delete
and tenant auto-filter are enforced by the model mixins.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_permission
from app.auth.permissions import Permission
from app.auth.providers import AuthenticatedIdentity
from app.core.database import get_db
from app.services import project_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["Projects"])


# --- Schemas ---


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    client_name: Optional[str] = None
    source_language: Optional[str] = None
    target_languages: List[str] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    client_name: Optional[str] = None
    status: Optional[str] = None
    source_language: Optional[str] = None
    target_languages: Optional[List[str]] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    client_name: Optional[str]
    status: str
    source_language: Optional[str]
    target_languages: List[str]
    document_count: int
    created_at: datetime
    updated_at: datetime


class AddDocumentRequest(BaseModel):
    document_id: str


def _to_response(project, document_count: int) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        client_name=project.client_name,
        status=project.status,
        source_language=project.source_language,
        target_languages=project.target_languages or [],
        document_count=document_count,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


# --- Endpoints ---


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(
        require_permission(Permission.DOCUMENT_CREATE)
    ),
):
    project = project_service.create_project(
        db,
        name=payload.name,
        description=payload.description,
        client_name=payload.client_name,
        source_language=payload.source_language,
        target_languages=payload.target_languages,
        created_by=str(user.user_id),
    )
    return _to_response(project, 0)


@router.get("", response_model=List[ProjectResponse])
def list_projects(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(get_current_user),
):
    projects = project_service.list_projects(db, status=status)
    out: List[ProjectResponse] = []
    for p in projects:
        out.append(_to_response(p, project_service.count_project_documents(db, p.id)))
    return out


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(get_current_user),
):
    project = project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _to_response(
        project, project_service.count_project_documents(db, project_id)
    )


@router.get("/{project_id}/summary")
def project_summary(
    project_id: str,
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(get_current_user),
):
    if project_service.get_project(db, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project_service.project_summary(db, project_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(
        require_permission(Permission.DOCUMENT_UPDATE)
    ),
):
    try:
        project = project_service.update_project(
            db, project_id, **payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _to_response(
        project, project_service.count_project_documents(db, project_id)
    )


@router.post("/{project_id}/documents", status_code=201)
def add_document(
    project_id: str,
    payload: AddDocumentRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(
        require_permission(Permission.DOCUMENT_UPDATE)
    ),
):
    try:
        membership = project_service.add_document_to_project(
            db, project_id, payload.document_id, added_by=str(user.user_id)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"project_id": membership.project_id, "document_id": membership.document_id}


@router.delete("/{project_id}/documents/{document_id}", status_code=204)
def remove_document(
    project_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(
        require_permission(Permission.DOCUMENT_UPDATE)
    ),
):
    removed = project_service.remove_document_from_project(db, project_id, document_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Document not in project")


@router.get("/{project_id}/documents")
def list_project_documents(
    project_id: str,
    db: Session = Depends(get_db),
    user: AuthenticatedIdentity = Depends(get_current_user),
):
    if project_service.get_project(db, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    docs = project_service.list_project_documents(db, project_id)
    return [
        {
            "id": d.id,
            "name": d.name,
            "status": d.status,
            "source_language": d.source_language,
            "target_language": d.target_language,
        }
        for d in docs
    ]
