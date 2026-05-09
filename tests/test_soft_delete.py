"""
TMX-3015 — soft-delete primitive: columns, hard-delete refusal, auto-filter.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker


SOFT_DELETE_COLUMNS = ("is_deleted", "deleted_at", "deleted_by")


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Return (engine, session) for a fresh SQLite database with all tables created.

    TMX-3012: enters `org_context(DEFAULT_ORG_ID)` for the duration so the
    auto-filter doesn't refuse queries. Soft-delete behaviour is independent
    of tenant scoping; this fixture isolates the soft-delete concern.
    """
    db_path = tmp_path / "tmx3015.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    import importlib
    import app.core.database as core_db
    importlib.reload(core_db)
    core_db.init_db()
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID
    Session = sessionmaker(bind=core_db.engine)
    session = Session()
    with org_context(DEFAULT_ORG_ID):
        yield core_db.engine, session
    session.close()


def test_every_tenant_scoped_table_has_soft_delete_columns(fresh_db):
    """All 22 tenant-scoped tables + organizations carry the three soft-delete columns.

    Excluded:
      - `language_packs` (system-level, not tenant-scoped)
      - `audit_events_v2`, `audit_anchors` (TMX-3100 — append-only by A1/A9;
        intentional non-application of SoftDeleteMixin)
      - `alembic_version` (alembic's own bookkeeping)
    """
    engine, _ = fresh_db
    ins = inspect(engine)
    excluded = {
        "language_packs",
        "audit_events_v2",
        "audit_anchors",
        "alembic_version",
    }

    for table in ins.get_table_names():
        if table in excluded:
            continue
        cols = {c["name"] for c in ins.get_columns(table)}
        for col in SOFT_DELETE_COLUMNS:
            assert col in cols, f"{table} missing {col}"


def test_language_packs_does_not_have_soft_delete(fresh_db):
    """Sanity: system-level table is excluded from the mixin."""
    engine, _ = fresh_db
    ins = inspect(engine)
    if "language_packs" not in ins.get_table_names():
        pytest.skip("language_packs not present in this build")
    cols = {c["name"] for c in ins.get_columns("language_packs")}
    for col in SOFT_DELETE_COLUMNS:
        assert col not in cols, f"language_packs should not have {col}"


def test_soft_delete_method_sets_columns(fresh_db):
    """obj.soft_delete(actor_id) sets is_deleted=True, deleted_at=now, deleted_by=actor_id."""
    engine, session = fresh_db
    from app.models.database import Document, DEFAULT_ORG_ID

    doc = Document(name="to-delete", source_language="en", organization_id=DEFAULT_ORG_ID)
    session.add(doc)
    session.commit()

    actor = "user-abc"
    doc.soft_delete(actor_id=actor)
    session.commit()

    # Re-fetch via include_deleted so we can see it after the auto-filter.
    fetched = (
        session.query(Document)
        .execution_options(include_deleted=True)
        .filter_by(id=doc.id)
        .one()
    )
    assert fetched.is_deleted is True
    assert fetched.deleted_at is not None
    assert fetched.deleted_by == actor


def test_hard_delete_is_refused(fresh_db):
    """session.delete(obj) on a soft-delete-capable model raises HardDeleteRefused."""
    engine, session = fresh_db
    from app.models.database import Document, DEFAULT_ORG_ID
    from app.models.soft_delete import HardDeleteRefused

    doc = Document(name="protected", source_language="en", organization_id=DEFAULT_ORG_ID)
    session.add(doc)
    session.commit()

    session.delete(doc)
    with pytest.raises(HardDeleteRefused):
        session.commit()
    session.rollback()


def test_default_query_excludes_soft_deleted(fresh_db):
    """A default session.query() does not return rows with is_deleted=True."""
    engine, session = fresh_db
    from app.models.database import Document, DEFAULT_ORG_ID

    alive = Document(name="alive", source_language="en", organization_id=DEFAULT_ORG_ID)
    dead = Document(name="dead", source_language="en", organization_id=DEFAULT_ORG_ID)
    session.add_all([alive, dead])
    session.commit()

    dead.soft_delete(actor_id="cleanup-job")
    session.commit()

    names = [d.name for d in session.query(Document).all()]
    assert "alive" in names
    assert "dead" not in names


def test_include_deleted_returns_soft_deleted_rows(fresh_db):
    """The execution_options opt-in returns soft-deleted rows for forensic queries."""
    engine, session = fresh_db
    from app.models.database import Document, DEFAULT_ORG_ID

    doc = Document(name="forensic", source_language="en", organization_id=DEFAULT_ORG_ID)
    session.add(doc)
    session.commit()
    doc.soft_delete(actor_id="cleanup-job")
    session.commit()

    # Default query: no result.
    assert session.query(Document).filter_by(name="forensic").first() is None

    # Forensic query: row visible.
    fetched = (
        session.query(Document)
        .execution_options(include_deleted=True)
        .filter_by(name="forensic")
        .one()
    )
    assert fetched.is_deleted is True


def test_soft_delete_does_not_affect_other_models(fresh_db):
    """Soft-deleting a Document doesn't accidentally hide unrelated Segments."""
    engine, session = fresh_db
    from app.models.database import Document, Segment, DEFAULT_ORG_ID

    doc = Document(name="container", source_language="en", organization_id=DEFAULT_ORG_ID)
    session.add(doc)
    session.commit()

    # Add a segment for an UNRELATED document so the count is observable.
    other_doc = Document(name="other", source_language="en", organization_id=DEFAULT_ORG_ID)
    session.add(other_doc)
    session.commit()
    other_seg = Segment(
        organization_id=DEFAULT_ORG_ID,
        document_id=other_doc.id,
        order_index=0,
        source_text="alive segment",
    )
    session.add(other_seg)
    session.commit()

    doc.soft_delete(actor_id="actor")
    session.commit()

    # Segment of `other_doc` is unaffected.
    assert session.query(Segment).filter_by(document_id=other_doc.id).count() == 1
