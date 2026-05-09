"""
Database connection and session management.
"""
import logging
import os
from contextlib import contextmanager
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)

# Load .env file
load_dotenv()

# Use PostgreSQL from .env, fallback to SQLite only if not set
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./transmax.db")
print(f"DEBUG: Using DATABASE_URL={DATABASE_URL}")

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL debugging
    # SQLite-specific args only if using SQLite
    **({} if "postgresql" in DATABASE_URL else {"connect_args": {"check_same_thread": False}})
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    Dependency for FastAPI endpoints.
    Yields a database session and ensures cleanup.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session(tenant_id: Optional[str] = None):
    """
    Context manager for database sessions outside of FastAPI.

    TMX-3012: when `tenant_id` is provided, the org-context ContextVar is set
    for the duration of the with-block. Every SELECT against a tenant-scoped
    table is auto-filtered to that tenant; every INSERT auto-injects the
    tenant id. Without `tenant_id`, queries against tenant-scoped tables
    raise `TenantContextMissing` (A3 — no silent cross-tenant leak).
    """
    from app.core.tenant_context import org_context

    db = SessionLocal()
    try:
        if tenant_id is not None:
            with org_context(tenant_id):
                yield db
                db.commit()
        else:
            yield db
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _enable_pgvector():
    """Try to enable pgvector extension. Returns True if available."""
    if "postgresql" not in DATABASE_URL:
        return False
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        print("pgvector extension enabled.")
        return True
    except Exception as e:
        print(f"WARNING: pgvector extension not available ({e}). Embedding columns will be skipped.")
        return False


def init_db():
    """
    Initialize the database by creating all tables.
    Tables are created individually so a failure on one (e.g. pgvector)
    doesn't block creation of the rest.
    """
    _enable_pgvector()

    # Import every model module so SQLAlchemy registers their tables on Base.metadata.
    # Previously only `database.py` was imported, which silently skipped the auth,
    # translation, audit, and models.py tables when init_db() ran from a fresh process.
    # TMX-3011 made this visible: tenant_id columns added to those modules wouldn't
    # appear in the SQLite dev DB until something else imported the module.
    import app.models.database  # noqa: F401
    import app.models.auth  # noqa: F401
    import app.models.audit  # noqa: F401
    import app.models.audit_v2  # noqa: F401  (TMX-3100)
    import app.models.translation  # noqa: F401
    import app.models.models  # noqa: F401
    # TMX-3012: importing this module registers the auto-inject + auto-filter
    # SQLAlchemy event listeners. Must be imported AFTER the models (which
    # mix in TenantScopedMixin); the listeners then fire on those classes.
    import app.models.tenant_scoped  # noqa: F401
    from app.models.database import Base

    failed = []
    for table in Base.metadata.sorted_tables:
        try:
            table.create(bind=engine, checkfirst=True)
        except Exception as e:
            failed.append(table.name)
            print(f"WARNING: Could not create table '{table.name}': {e}")

    if failed:
        print(f"Database init complete with skipped tables: {failed}")
    else:
        print("Database tables created successfully.")

    _seed_default_org()


def _seed_default_org() -> None:
    """Seed the system default-org row (TMX-3010).

    Idempotent — uses INSERT ... ON CONFLICT / INSERT OR IGNORE so re-running
    init_db() in dev or CI does not raise. This mirrors the alembic migration
    so the row exists regardless of which init path was used (alembic upgrade
    vs. SessionLocal-only test setup).
    """
    from datetime import datetime, timezone
    from sqlalchemy import text
    from app.models.database import DEFAULT_ORG_ID

    now_iso = datetime.now(timezone.utc).isoformat()
    is_postgres = "postgresql" in DATABASE_URL
    sql = (
        "INSERT INTO organizations (id, name, slug, org_kind, is_active, created_at, updated_at) "
        "VALUES (:id, 'default', 'default', 'system', :truthy, :ts, :ts) "
        + ("ON CONFLICT (id) DO NOTHING" if is_postgres else "")
    )
    if not is_postgres:
        sql = sql.replace("INSERT INTO", "INSERT OR IGNORE INTO", 1)

    try:
        with engine.begin() as conn:
            conn.execute(
                text(sql).bindparams(id=DEFAULT_ORG_ID, ts=now_iso, truthy=True if is_postgres else 1)
            )
    except Exception as e:
        logger.warning("default-org seed failed (%s). TMX-3011 backfill will fail until resolved.", e)
