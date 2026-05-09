"""
TMX-3011 — every tenant-scoped table has NOT NULL `organization_id` FK to organizations.id.

Verified against a fresh in-process SQLite database created by `init_db()`. A
side-effect defect closed in this ticket: `init_db()` previously didn't import
`auth.py`, `audit.py`, `translation.py`, `models.py`, so their tables were
silently skipped from `Base.metadata.sorted_tables`. The first test here is a
regression guard against that.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker


# Tables that are SYSTEM-LEVEL (not tenant-scoped). Mirror is in the alembic revision
# and in TMX-3011's worksheet.
SYSTEM_TABLES = {"organizations", "language_packs", "alembic_version"}


@pytest.fixture
def fresh_db(fresh_engine_for_db):
    """Return (engine, session) for a fresh SQLite database with all tables created.

    TMX-AUDIT-CLEANUP-ROUTES: delegates to shared conftest fixture which uses
    in-place engine swap instead of `importlib.reload(core_db)`. The reload
    pattern broke FastAPI dependency overrides in unrelated tests.
    """
    core_db = fresh_engine_for_db
    Session = sessionmaker(bind=core_db.engine)
    session = Session()
    yield core_db.engine, session
    session.close()


def test_init_db_registers_every_module_table(fresh_db):
    """Regression guard: init_db() must import every model module so all tables register.

    A prior defect had init_db() importing only database.py, which silently dropped
    the tables defined in auth.py / audit.py / translation.py / models.py.
    """
    engine, _ = fresh_db
    ins = inspect(engine)
    table_names = set(ins.get_table_names())
    # We expect at least these representative tables from each module.
    assert "organizations" in table_names                       # database.py
    assert "users" in table_names                                # auth.py
    assert "audit_records" in table_names                        # audit.py
    assert "translation_jobs" in table_names                     # translation.py
    assert "translation_jobs_queue" in table_names               # models.py


def test_every_domain_table_has_organization_id(fresh_db):
    """Every non-system table must carry organization_id NOT NULL."""
    engine, _ = fresh_db
    ins = inspect(engine)
    domain_tables = [t for t in ins.get_table_names() if t not in SYSTEM_TABLES]
    assert len(domain_tables) >= 22, f"Expected ≥22 domain tables, got {len(domain_tables)}: {domain_tables}"

    for table in domain_tables:
        cols = {c["name"]: c for c in ins.get_columns(table)}
        assert "organization_id" in cols, f"{table} is missing organization_id"
        assert cols["organization_id"]["nullable"] is False, f"{table}.organization_id is nullable"


def test_organization_id_fk_present_on_every_domain_table(fresh_db):
    """Every domain table must have an FK from organization_id to organizations.id."""
    engine, _ = fresh_db
    ins = inspect(engine)
    for table in ins.get_table_names():
        if table in SYSTEM_TABLES:
            continue
        fks = ins.get_foreign_keys(table)
        org_fks = [
            fk for fk in fks
            if fk["referred_table"] == "organizations"
            and "organization_id" in fk["constrained_columns"]
        ]
        assert org_fks, f"{table} missing organization_id FK to organizations"


def test_inserting_without_org_id_raises(fresh_db):
    """A row inserted without organization_id raises (no context + no explicit value).

    TMX-3012 changed the failure mode from `IntegrityError` (NOT NULL) to
    `TenantContextMissing` (raised by the auto-inject listener BEFORE the SQL
    fires). Either is a valid "rejected" outcome per AC-6 of TMX-3011.
    """
    engine, session = fresh_db
    from app.core.tenant_context import TenantContextMissing
    from app.models.database import Document

    bad = Document(name="orphan", source_language="en")
    session.add(bad)
    with pytest.raises((IntegrityError, TenantContextMissing)):
        session.commit()
    session.rollback()


def test_inserting_with_unknown_org_id_raises_fk_error(fresh_db):
    """An organization_id that doesn't exist in organizations must be rejected."""
    engine, session = fresh_db
    from app.models.database import Document

    # Enable FK enforcement on this SQLite connection (off by default).
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))

    Session = sessionmaker(bind=engine)
    fk_session = Session()
    fk_session.execute(text("PRAGMA foreign_keys = ON"))

    # An org id that does not exist in `organizations`.
    ghost_id = str(uuid.uuid4())
    bad = Document(name="phantom", source_language="en", organization_id=ghost_id)
    fk_session.add(bad)
    with pytest.raises(IntegrityError):
        fk_session.commit()
    fk_session.rollback()
    fk_session.close()


def test_inserting_with_default_org_id_succeeds(fresh_db):
    """Happy path: passing the seeded default-org id allows the insert."""
    engine, session = fresh_db
    from app.core.tenant_context import org_context
    from app.models.database import Document, DEFAULT_ORG_ID

    doc = Document(name="ok", source_language="en", organization_id=DEFAULT_ORG_ID)
    session.add(doc)
    session.commit()

    # TMX-3012: SELECTs against tenant-scoped tables require a context.
    with org_context(DEFAULT_ORG_ID):
        fetched = session.query(Document).filter_by(name="ok").one()
        assert fetched.organization_id == DEFAULT_ORG_ID


def test_language_packs_excluded_from_tenant_scoping(fresh_db):
    """language_packs is system-level config; it must NOT have organization_id."""
    engine, _ = fresh_db
    ins = inspect(engine)
    if "language_packs" not in ins.get_table_names():
        pytest.skip("language_packs not present in this DB build")
    cols = [c["name"] for c in ins.get_columns("language_packs")]
    assert "organization_id" not in cols, "language_packs must remain system-level (TMX-3011 explicit exclusion)"
