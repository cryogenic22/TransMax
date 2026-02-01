#!/usr/bin/env python
"""Create TransMax v2.0 tables in PostgreSQL."""
from dotenv import load_dotenv
load_dotenv()

from app.core.database import engine
from app.models.database import Base, Document, Segment, ChangeLog

print("Creating tables...")
Base.metadata.create_all(engine)
print("Tables created successfully!")

# Verify
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"Tables in database: {tables}")
