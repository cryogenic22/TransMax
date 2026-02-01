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


def init_db():
    """
    Initialize the database by creating all tables.
    """
    try:
        from app.models.database import Base
        Base.metadata.create_all(bind=engine)
        print("Database tables created successfully.")
    except Exception as e:
        print(f"WARNING: Database initialization failed. App will start but DB features may not work. Error: {e}")
