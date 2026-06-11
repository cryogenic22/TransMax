"""
TMX-AUDIT-DB-DOCID-LOOKUP — get_doc_id_from_job + get_pending_reviews.

Proves the stub `pass`-body (which silently returned None) is gone:
- get_doc_id_from_job resolves a real Document id, returns None for unknown.
- get_pending_reviews returns the flagged (BLOCKED/REVIEW_REQUIRED) segments,
  [] (not None) when the identifier resolves to no document.
- tenant scoping: a doc in org A does not resolve under org B's context.

db_service binds `SessionLocal` at import from app.models.database (which
re-exports app.core.database.SessionLocal). The `fresh_engine_for_db` fixture
swaps app.core.database.SessionLocal in place, which does NOT rebind the alias
already imported into db_service — so we monkeypatch the db_service alias to the
fresh sessionmaker (get_session resolves it in db_service globals at call time).
"""
import uuid


from app.core.tenant_context import org_context


def _bind_db_service_to_fresh(core_db, monkeypatch):
    monkeypatch.setattr(
        "app.services.db_service.SessionLocal", core_db.SessionLocal, raising=True
    )


def _make_org(core_db, slug):
    from app.models.database import Organization

    session = core_db.SessionLocal()
    org = Organization(name=slug, slug=slug, org_kind="customer")
    session.add(org)
    session.commit()
    org_id = str(org.id)
    session.close()
    return org_id


def _make_doc_with_segments(core_db, org_id, statuses):
    from app.models.database import Document, Segment

    session = core_db.SessionLocal()
    with org_context(org_id):
        doc = Document(
            name="PIL.pdf",
            source_language="en",
            target_language="es",
            status="blocked",
            organization_id=org_id,
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id
        for i, st in enumerate(statuses):
            session.add(
                Segment(
                    document_id=doc_id,
                    organization_id=org_id,
                    order_index=i,
                    source_text=f"src-{i}",
                    translated_text=f"tgt-{i}",
                    status=st,
                )
            )
        session.commit()
    session.close()
    return doc_id


def test_get_doc_id_from_job_resolves_known_and_unknown(
    fresh_engine_for_db, monkeypatch
):
    core_db = fresh_engine_for_db
    _bind_db_service_to_fresh(core_db, monkeypatch)
    from app.services.db_service import get_db_service

    org_id = _make_org(core_db, "acme-docid")
    doc_id = _make_doc_with_segments(core_db, org_id, ["BLOCKED"])

    with org_context(org_id):
        db = get_db_service()
        # AC-1: known id resolves to itself
        assert db.get_doc_id_from_job(doc_id) == doc_id
        # AC-1: unknown id resolves to None (explicit, not a guess)
        assert db.get_doc_id_from_job(str(uuid.uuid4())) is None


def test_get_pending_reviews_returns_flagged_segments(
    fresh_engine_for_db, monkeypatch
):
    core_db = fresh_engine_for_db
    _bind_db_service_to_fresh(core_db, monkeypatch)
    from app.services.review_service import ReviewService

    org_id = _make_org(core_db, "acme-pending")
    # 2 flagged + 1 plain TRANSLATED
    doc_id = _make_doc_with_segments(
        core_db, org_id, ["BLOCKED", "REVIEW_REQUIRED", "TRANSLATED"]
    )

    with org_context(org_id):
        reviews = ReviewService().get_pending_reviews(doc_id)

    # AC-2: returns a list (never None), only the flagged segments
    assert isinstance(reviews, list)
    statuses = {r["status"] for r in reviews}
    assert statuses == {"BLOCKED", "REVIEW_REQUIRED"}
    assert len(reviews) == 2


def test_get_pending_reviews_unknown_job_returns_empty_list(
    fresh_engine_for_db, monkeypatch
):
    core_db = fresh_engine_for_db
    _bind_db_service_to_fresh(core_db, monkeypatch)
    from app.services.review_service import ReviewService

    org_id = _make_org(core_db, "acme-empty")
    with org_context(org_id):
        # AC-3: no document resolves -> [] (not None), logged at WARNING
        reviews = ReviewService().get_pending_reviews(str(uuid.uuid4()))
    assert reviews == []


def test_get_doc_id_is_tenant_scoped(fresh_engine_for_db, monkeypatch):
    core_db = fresh_engine_for_db
    _bind_db_service_to_fresh(core_db, monkeypatch)
    from app.services.db_service import get_db_service

    org_a = _make_org(core_db, "org-a-docid")
    org_b = _make_org(core_db, "org-b-docid")
    doc_id = _make_doc_with_segments(core_db, org_a, ["BLOCKED"])

    db = get_db_service()
    # AC-4: under org B's context, org A's doc does not resolve
    with org_context(org_b):
        assert db.get_doc_id_from_job(doc_id) is None
    # sanity: it DOES resolve under org A
    with org_context(org_a):
        assert db.get_doc_id_from_job(doc_id) == doc_id
