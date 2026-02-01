import pytest
import os
import uuid
from app.services.db_service import DatabaseService

# Skip if no DB configured (optional, but good for CI)
# @pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
def test_create_job():
    service = DatabaseService()
    try:
        # Create a mock request
        request_data = {
            "request_id": str(uuid.uuid4()),
            "source_language": "en",
            "target_language": "fr",
            "domain": "test",
            "audience": "test",
            "content": "Hello"
        }
        
        job_id = service.create_job(request_data)
        assert job_id is not None
        
        # Verify persistence (by fetching - though method not explicitly exposing fetch, we can check session)
        session = service.get_session()
        from app.models.models import TranslationJob
        job = session.query(TranslationJob).filter_by(job_id=job_id).first()
        assert job is not None
        assert job.source_language == "en"
        session.close()
        
    except Exception as e:
        pytest.fail(f"Database operation failed: {e}")
