#!/usr/bin/env python
"""Quick test to verify database models load correctly."""
try:
    from app.models.database import Document, Segment, ChangeLog, Base
    print("✓ Models imported successfully")
    print(f"  - Document table: {Document.__tablename__}")
    print(f"  - Segment table: {Segment.__tablename__}")
    print(f"  - ChangeLog table: {ChangeLog.__tablename__}")
    
    from app.core.database import engine, init_db
    print("✓ Database engine loaded")
    
    # Try creating tables
    init_db()
    print("✓ Database tables created")
    
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
