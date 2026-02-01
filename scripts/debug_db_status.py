import sys
import os
import uuid
import logging

# Add project root
sys.path.append(os.getcwd())

from app.services.db_service import DatabaseService
from app.models.database import Document, DocumentStatus, Base, engine

# Setup logging
logging.basicConfig(level=logging.INFO)

def run_debug():
    print("Initializing DB...")
    Base.metadata.create_all(bind=engine)
    
    db = DatabaseService()
    session = db.get_session()
    
    doc_id = str(uuid.uuid4())
    print(f"Creating doc {doc_id}...")
    doc = Document(
        id=doc_id, 
        name="debug_doc.txt", 
        source_language="en", 
        status=DocumentStatus.UPLOADED
    )
    session.add(doc)
    session.commit()
    session.close()
    
    print("Updating status to PROCESSING (str)...")
    try:
        db.update_document_status(doc_id, "processing")
        print("Success!")
    except Exception as e:
        print(f"Failed: {e}")
        import traceback
        traceback.print_exc()

    print("Updating status to PROCESSING (Enum)...")
    try:
        db.update_document_status(doc_id, DocumentStatus.PROCESSING)
        print("Success!")
    except Exception as e:
        print(f"Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_debug()
