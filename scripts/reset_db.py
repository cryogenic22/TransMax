
import sys
import os
from sqlalchemy import text

# Add project root
sys.path.append(os.getcwd())

from app.models.database import engine, create_tables
# Import models to register them with Base
from app.models.models import *

def reset_database():
    print("Resetting Database Schema (Hard Reset)...")
    try:
        with engine.connect() as conn:
            # Force drop known tables with CASCADE
            tables = [
                "audit_log_entries",
                "job_config_snapshots",
                "glossary_terms",
                "glossaries",
                "change_logs",
                "tm_segments",
                "segments",
                "documents",
                "translation_jobs_queue",
                "audit_records_queue"
            ]
            
            for t in tables:
                print(f"Dropping {t}...")
                conn.execute(text(f"DROP TABLE IF EXISTS {t} CASCADE"))
                
            conn.commit()
            
        print("Creating all tables...")
        create_tables(engine)
        print("Database Reset Complete.")
        
    except Exception as e:
        print(f"Error resetting database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    reset_database()
