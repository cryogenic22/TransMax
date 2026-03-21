"""
Database connection and session management.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

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
