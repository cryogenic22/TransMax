"""
TMX-3010 — tests for the `organizations` table and the `GUID` portable type.

Each test runs against an in-memory SQLite engine so it does not touch the dev
database. The migration's seed of the system default-org is exercised via a
direct DDL + INSERT path that mirrors the alembic revision.
"""
from __future__ import annotations

import importlib
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def in_memory_session():
    """Return a session bound to a fresh in-memory SQLite database."""
    engine = create_engine("sqlite:///:memory:")
    from app.models.database import Base
    # Create only the organizations table for isolation; other tables are
    # exercised in their own ticket-level tests.
    Base.metadata.tables["organizations"].create(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session, engine
    session.close()


def test_default_org_constants_match_handoff():
    """Constants we expose for migrations and tests must match the handoff spec."""
    from app.models.database import DEFAULT_ORG_ID, ORG_KINDS
    assert DEFAULT_ORG_ID == "00000000-0000-0000-0000-000000000001"
    assert ORG_KINDS == ("system", "customer", "partner")


def test_create_organization_round_trip(in_memory_session):
    """An Organization round-trips through SQLite preserving its UUID-as-string id."""
    session, _ = in_memory_session
    from app.models.database import Organization

    org_id = str(uuid.uuid4())
    org = Organization(
        id=org_id,
        name="Acme Pharma",
        slug="acme-pharma",
        org_kind="customer",
    )
    session.add(org)
    session.commit()

    fetched = session.query(Organization).filter_by(slug="acme-pharma").one()
    assert fetched.id == org_id
    assert fetched.name == "Acme Pharma"
    assert fetched.org_kind == "customer"
    assert fetched.is_active is True


def test_slug_unique_constraint(in_memory_session):
    """Two organizations cannot share a slug."""
    session, _ = in_memory_session
    from app.models.database import Organization

    session.add(Organization(id=str(uuid.uuid4()), name="A", slug="dup", org_kind="customer"))
    session.commit()
    session.add(Organization(id=str(uuid.uuid4()), name="B", slug="dup", org_kind="customer"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_org_kind_check_constraint(in_memory_session):
    """The CheckConstraint rejects values outside the allowed set."""
    session, engine = in_memory_session
    # SQLite enforces CHECK constraints by default since 3.3.0.
    from app.models.database import Organization

    bad = Organization(id=str(uuid.uuid4()), name="X", slug="x", org_kind="invalid_kind")
    session.add(bad)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_seed_default_org_idempotent_on_sqlite(in_memory_session):
    """The migration's INSERT OR IGNORE seed must be safely re-runnable."""
    session, engine = in_memory_session
    from app.models.database import DEFAULT_ORG_ID, Organization

    seed_sql = text(
        "INSERT OR IGNORE INTO organizations "
        "(id, name, slug, org_kind, is_active, created_at, updated_at) "
        "VALUES (:id, 'default', 'default', 'system', 1, :ts, :ts)"
    ).bindparams(id=DEFAULT_ORG_ID, ts="2026-05-05T00:00:00+00:00")
    with engine.begin() as conn:
        conn.execute(seed_sql)
        conn.execute(seed_sql)  # second time must not raise

    fetched = session.query(Organization).filter_by(id=DEFAULT_ORG_ID).one()
    assert fetched.slug == "default"
    assert fetched.org_kind == "system"


def test_guid_type_resolves_per_dialect():
    """GUID is CHAR(36) on SQLite and UUID on Postgres (descriptor only)."""
    from sqlalchemy.dialects import postgresql, sqlite
    from app.models.types import GUID

    guid = GUID()
    sqlite_descriptor = guid.load_dialect_impl(sqlite.dialect())
    pg_descriptor = guid.load_dialect_impl(postgresql.dialect())

    # On SQLite we use a fixed-length 36-char column.
    assert sqlite_descriptor.length == 36
    # On Postgres we use the native UUID type.
    assert isinstance(pg_descriptor, postgresql.UUID)


def test_no_circular_import_between_database_and_translation():
    """Importing translation.py after database.py must not raise — types.py must be import-clean."""
    import app.models.database  # noqa: F401
    importlib.import_module("app.models.translation")
    importlib.import_module("app.models.audit")


def test_init_db_seeds_default_org(tmp_path, monkeypatch):
    """init_db() must seed the system default-org row idempotently on a fresh SQLite db."""
    db_path = tmp_path / "init_seed.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    # Force a fresh import of the database module so it picks up the new URL.
    import importlib
    import app.core.database as core_db
    importlib.reload(core_db)
    from app.models.database import DEFAULT_ORG_ID, Organization

    core_db.init_db()
    core_db.init_db()  # second call must not raise — proves idempotency

    Session = sessionmaker(bind=core_db.engine)
    session = Session()
    try:
        seeded = session.query(Organization).filter_by(id=DEFAULT_ORG_ID).one()
        assert seeded.slug == "default"
        assert seeded.org_kind == "system"
        assert seeded.is_active is True
        # Exactly one default-org row.
        assert session.query(Organization).filter_by(id=DEFAULT_ORG_ID).count() == 1
    finally:
        session.close()
