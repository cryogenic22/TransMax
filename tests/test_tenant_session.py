"""
TMX-3012 — tests for the tenant-scoped session factory.

Covers:
  - tenant context: set/get/clear/contextmanager
  - auto-inject organization_id on INSERT when context is set
  - explicit organization_id wins over auto-inject (legacy fixtures keep working)
  - TenantContextMissing raised on INSERT when no context AND no explicit org_id
  - auto-filter SELECTs by tenant; cross-tenant rows hidden
  - TenantContextMissing raised on SELECT against tenant-scoped table without context
  - include_other_tenants=True bypass works for forensic/admin paths
  - tenant filter composes with TMX-3015 soft-delete filter (both apply)
  - get_db_session(tenant_id) sets context for the duration
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "tmx3012.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    import importlib
    import app.core.database as core_db
    importlib.reload(core_db)
    core_db.init_db()
    Session = sessionmaker(bind=core_db.engine)
    yield core_db, Session


def _make_doc(name: str, organization_id=None):
    """Construct a Document — optionally with an explicit org_id."""
    from app.models.database import Document
    kwargs = dict(name=name, source_language="en")
    if organization_id is not None:
        kwargs["organization_id"] = organization_id
    return Document(**kwargs)


def _seed_org(core_db, org_id: str, slug: str = None) -> str:
    """Insert an Organization. Bypasses tenant filter (organizations is the FK target)."""
    from app.models.database import Organization
    Session = sessionmaker(bind=core_db.engine)
    s = Session()
    try:
        s.add(Organization(id=org_id, name=f"Org {slug or org_id[:8]}", slug=slug or f"org-{org_id[:8]}"))
        s.commit()
    finally:
        s.close()
    return org_id


# ---------- tenant context primitive ----------

def test_context_set_get_clear():
    from app.core.tenant_context import current_org_id, set_org_id, clear_org

    assert current_org_id() is None
    token = set_org_id("acme")
    assert current_org_id() == "acme"
    clear_org(token)
    assert current_org_id() is None


def test_org_context_manager_restores_prior():
    from app.core.tenant_context import current_org_id, org_context, set_org_id, clear_org

    outer_token = set_org_id("outer")
    try:
        assert current_org_id() == "outer"
        with org_context("inner"):
            assert current_org_id() == "inner"
        assert current_org_id() == "outer"  # restored
    finally:
        clear_org(outer_token)
    assert current_org_id() is None


# ---------- INSERT auto-injection ----------

def test_insert_injects_org_id_from_context(fresh_db):
    core_db, Session = fresh_db
    from app.core.tenant_context import org_context
    from app.models.database import Document, DEFAULT_ORG_ID

    s = Session()
    try:
        with org_context(DEFAULT_ORG_ID):
            doc = _make_doc("auto-injected")
            assert doc.organization_id is None
            s.add(doc)
            s.commit()
            s.refresh(doc)
            assert doc.organization_id == DEFAULT_ORG_ID
    finally:
        s.close()


def test_insert_preserves_explicit_org_id(fresh_db):
    """Legacy fixtures that pass organization_id=DEFAULT_ORG_ID keep working."""
    core_db, Session = fresh_db
    from app.core.tenant_context import org_context
    from app.models.database import Document, DEFAULT_ORG_ID

    s = Session()
    try:
        # No tenant context, but explicit org_id is provided. Insert succeeds.
        doc = _make_doc("explicit", organization_id=DEFAULT_ORG_ID)
        s.add(doc)
        s.commit()
        # Read back via context to verify the row landed correctly.
        doc_id = doc.id
    finally:
        s.close()

    s = Session()
    try:
        with org_context(DEFAULT_ORG_ID):
            fetched = s.query(Document).filter_by(id=doc_id).one()
            assert fetched.organization_id == DEFAULT_ORG_ID
            assert fetched.name == "explicit"
    finally:
        s.close()


def test_insert_without_context_or_explicit_raises(fresh_db):
    core_db, Session = fresh_db
    from app.core.tenant_context import TenantContextMissing
    from app.models.database import Document

    s = Session()
    try:
        s.add(_make_doc("orphan"))
        with pytest.raises(TenantContextMissing):
            s.commit()
        s.rollback()
    finally:
        s.close()


# ---------- SELECT auto-filter ----------

def test_select_filtered_by_current_tenant(fresh_db):
    """A SELECT inside org_context(A) returns only A's rows."""
    core_db, Session = fresh_db
    from app.core.tenant_context import org_context
    from app.models.database import Document, DEFAULT_ORG_ID

    org_b = _seed_org(core_db, "11111111-1111-1111-1111-111111111111", "org-b")

    # Seed: one doc per org
    s = Session()
    try:
        with org_context(DEFAULT_ORG_ID):
            s.add(_make_doc("alpha-doc"))
            s.commit()
        with org_context(org_b):
            s.add(_make_doc("beta-doc"))
            s.commit()
    finally:
        s.close()

    # Query as A → only sees alpha-doc
    s = Session()
    try:
        with org_context(DEFAULT_ORG_ID):
            names = [d.name for d in s.query(Document).all()]
            assert "alpha-doc" in names
            assert "beta-doc" not in names
    finally:
        s.close()

    # Query as B → only sees beta-doc
    s = Session()
    try:
        with org_context(org_b):
            names = [d.name for d in s.query(Document).all()]
            assert "beta-doc" in names
            assert "alpha-doc" not in names
    finally:
        s.close()


def test_select_without_context_against_tenant_scoped_raises(fresh_db):
    core_db, Session = fresh_db
    from app.core.tenant_context import TenantContextMissing
    from app.models.database import Document

    s = Session()
    try:
        with pytest.raises(TenantContextMissing):
            s.query(Document).all()
    finally:
        s.close()


def test_include_other_tenants_bypass(fresh_db):
    """Forensic queries can opt out of the tenant filter."""
    core_db, Session = fresh_db
    from app.core.tenant_context import org_context
    from app.models.database import Document, DEFAULT_ORG_ID

    org_b = _seed_org(core_db, "22222222-2222-2222-2222-222222222222", "org-c")

    s = Session()
    try:
        with org_context(DEFAULT_ORG_ID):
            s.add(_make_doc("alpha-doc-2"))
            s.commit()
        with org_context(org_b):
            s.add(_make_doc("gamma-doc-2"))
            s.commit()
    finally:
        s.close()

    # Bypass: see all tenants
    s = Session()
    try:
        with org_context(DEFAULT_ORG_ID):
            all_docs = s.query(Document).execution_options(include_other_tenants=True).all()
            names = {d.name for d in all_docs}
            assert "alpha-doc-2" in names
            assert "gamma-doc-2" in names
    finally:
        s.close()


# ---------- composition with soft-delete ----------

def test_tenant_and_soft_delete_compose(fresh_db):
    """A row must be in-tenant AND not-soft-deleted to appear in default queries."""
    core_db, Session = fresh_db
    from app.core.tenant_context import org_context
    from app.models.database import Document, DEFAULT_ORG_ID

    s = Session()
    try:
        with org_context(DEFAULT_ORG_ID):
            doc = _make_doc("alive-and-mine")
            s.add(doc)
            s.commit()
            doc2 = _make_doc("deleted-but-mine")
            s.add(doc2)
            s.commit()
            doc2.soft_delete(actor_id="test")
            s.commit()
    finally:
        s.close()

    s = Session()
    try:
        with org_context(DEFAULT_ORG_ID):
            names = [d.name for d in s.query(Document).all()]
            assert "alive-and-mine" in names
            assert "deleted-but-mine" not in names

            # Forensic: include deleted, my-tenant only.
            forensic = (
                s.query(Document)
                .execution_options(include_deleted=True)
                .all()
            )
            names = {d.name for d in forensic}
            assert "alive-and-mine" in names
            assert "deleted-but-mine" in names
    finally:
        s.close()


# ---------- get_db_session(tenant_id) ----------

def test_get_db_session_with_tenant_id_sets_context(fresh_db):
    core_db, _ = fresh_db
    from app.core.tenant_context import current_org_id
    from app.models.database import Document, DEFAULT_ORG_ID

    with core_db.get_db_session(tenant_id=DEFAULT_ORG_ID) as db:
        assert current_org_id() == DEFAULT_ORG_ID
        db.add(_make_doc("via-factory"))
        # commit handled by the context manager

    # Context cleared after exit.
    assert current_org_id() is None


def test_get_db_session_no_tenant_id_does_not_set_context(fresh_db):
    """Bare get_db_session() preserves existing back-compat for non-tenant queries."""
    core_db, _ = fresh_db
    from app.core.tenant_context import current_org_id
    from app.models.database import Organization

    with core_db.get_db_session() as db:
        assert current_org_id() is None
        # Query a non-tenant-scoped table — no context required.
        orgs = db.query(Organization).all()
        assert len(orgs) >= 1  # at least the default-org seed
