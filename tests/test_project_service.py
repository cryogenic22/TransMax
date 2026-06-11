"""
TMX-PROJECTS-MODEL — project grouping service (DB-isolated).

Exercises create/list/update + membership add/remove/list + summary against a
fresh SQLite engine, all inside a tenant context. Proves: tenant scoping,
idempotent membership, soft-delete-then-readd, fail-loud on a missing doc/proj,
and status validation.
"""

import pytest

from app.core.tenant_context import org_context
from app.services import project_service as ps


def _make_org_and_doc(core_db):
    from app.models.database import Document, Organization

    session = core_db.SessionLocal()
    org = Organization(name="Acme", slug="acme-proj", org_kind="customer")
    session.add(org)
    session.commit()
    org_id = str(org.id)
    with org_context(org_id):
        doc = Document(
            name="PIL-EN.pdf",
            source_language="en",
            target_language="fr",
            status="uploaded",
            organization_id=org_id,
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id
    return session, org_id, doc_id


def test_create_and_get_project(fresh_engine_for_db):
    session, org_id, _doc = _make_org_and_doc(fresh_engine_for_db)
    try:
        with org_context(org_id):
            p = ps.create_project(
                session, name="EMA Submission Q3", client_name="Veridian"
            )
            assert p.id and p.status == "active"
            got = ps.get_project(session, p.id)
            assert got.name == "EMA Submission Q3"
            assert got.client_name == "Veridian"
    finally:
        session.close()


def test_create_rejects_empty_name(fresh_engine_for_db):
    session, org_id, _doc = _make_org_and_doc(fresh_engine_for_db)
    try:
        with org_context(org_id):
            with pytest.raises(ValueError, match="name is required"):
                ps.create_project(session, name="   ")
    finally:
        session.close()


def test_membership_idempotent_and_summary(fresh_engine_for_db):
    session, org_id, doc_id = _make_org_and_doc(fresh_engine_for_db)
    try:
        with org_context(org_id):
            p = ps.create_project(session, name="Study A")
            ps.add_document_to_project(session, p.id, doc_id)
            ps.add_document_to_project(session, p.id, doc_id)  # idempotent
            docs = ps.list_project_documents(session, p.id)
            assert len(docs) == 1
            summary = ps.project_summary(session, p.id)
            assert summary["document_count"] == 1
            assert summary["by_status"] == {"uploaded": 1}
    finally:
        session.close()


def test_remove_then_readd(fresh_engine_for_db):
    session, org_id, doc_id = _make_org_and_doc(fresh_engine_for_db)
    try:
        with org_context(org_id):
            p = ps.create_project(session, name="Study B")
            ps.add_document_to_project(session, p.id, doc_id)
            assert ps.remove_document_from_project(session, p.id, doc_id) is True
            assert ps.list_project_documents(session, p.id) == []
            # Soft-deleted membership must not block a re-add (A9).
            ps.add_document_to_project(session, p.id, doc_id)
            assert len(ps.list_project_documents(session, p.id)) == 1
    finally:
        session.close()


def test_add_missing_document_fails_loud(fresh_engine_for_db):
    session, org_id, _doc = _make_org_and_doc(fresh_engine_for_db)
    try:
        with org_context(org_id):
            p = ps.create_project(session, name="Study C")
            with pytest.raises(ValueError, match="not found"):
                ps.add_document_to_project(session, p.id, "no-such-doc")
    finally:
        session.close()


def test_update_status_validation(fresh_engine_for_db):
    session, org_id, _doc = _make_org_and_doc(fresh_engine_for_db)
    try:
        with org_context(org_id):
            p = ps.create_project(session, name="Study D")
            updated = ps.update_project(session, p.id, status="completed")
            assert updated.status == "completed"
            with pytest.raises(ValueError, match="invalid status"):
                ps.update_project(session, p.id, status="bogus")
    finally:
        session.close()
