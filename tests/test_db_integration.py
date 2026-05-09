import pytest
import os
import uuid
from app.services.db_service import DatabaseService

def test_create_job():
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID

    service = DatabaseService()
    try:
        request_data = {
            "request_id": str(uuid.uuid4()),
            "source_language": "en",
            "target_language": "fr",
            "domain": "test",
            "audience": "test",
            "content": "Hello"
        }

        with org_context(DEFAULT_ORG_ID):
            job_id = service.create_job(request_data)
            assert job_id is not None

            # Verify persistence
            session = service.get_session()
            from app.models.models import TranslationJobQueue
            job = session.query(TranslationJobQueue).filter_by(job_id=job_id).first()
            assert job is not None
            assert job.source_language == "en"
            session.close()

    except Exception as e:
        pytest.fail(f"Database operation failed: {e}")
