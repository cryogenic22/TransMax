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
    """
    try:
        has_pgvector = _enable_pgvector()

        from app.models.database import Base

        if not has_pgvector:
            # Remove vector columns from metadata so create_all doesn't fail
            from pgvector.sqlalchemy import Vector
            for table in Base.metadata.tables.values():
                cols_to_remove = [c for c in table.columns if isinstance(c.type, Vector)]
                for col in cols_to_remove:
                    table._columns.remove(col)

        Base.metadata.create_all(bind=engine)
        print("Database tables created successfully.")
    except Exception as e:
        print(f"WARNING: Database initialization failed. App will start but DB features may not work. Error: {e}")
