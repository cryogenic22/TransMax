"""
Database connection and session management.
"""
import logging
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

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
def get_db_session():
    """
    Context manager for database sessions outside of FastAPI.
    """
    db = SessionLocal()
    try:
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
