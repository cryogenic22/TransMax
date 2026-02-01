#!/usr/bin/env python
"""Test PostgreSQL connection and create tables."""
import os
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5433/transmax"

try:
    from sqlalchemy import create_engine, text
    
    # First try connecting to default 'postgres' database to create 'transmax'
    admin_engine = create_engine("postgresql://postgres:postgres@localhost:5433/postgres")
    with admin_engine.connect() as conn:
        # Check if transmax database exists
        result = conn.execute(text("SELECT 1 FROM pg_database WHERE datname='transmax'"))
        if not result.fetchone():
            conn.execute(text("COMMIT"))  # End current transaction
            conn.execute(text("CREATE DATABASE transmax"))
            print("Created 'transmax' database")
        else:
            print("Database 'transmax' already exists")
    
    # Now connect to transmax and create tables
    from app.core.database import engine
    from app.models.database import Base
    Base.metadata.create_all(engine)
    print("Tables created successfully in PostgreSQL!")
    
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
