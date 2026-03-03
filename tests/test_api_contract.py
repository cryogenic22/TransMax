import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from app.main import app
from app.models.database import Document, DocumentStatus, Segment
from datetime import datetime

client = TestClient(app)

REQ_ID = "test-req-001"

@pytest.fixture(autouse=True)
def mock_init_db():
    with patch("app.main.init_db"):
        yield

def test_create_job_tmx010():
    """Verify v1/translations endpoint contract."""
    with patch("app.api.v1.translations.run_pipeline_background") as mock_runner:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        from app.core.database import get_db
        app.dependency_overrides[get_db] = lambda: mock_db

        payload = {
            "source_language": "en",
            "target_language": "fr",
            "request_id": "req-new-1",
            "text_content": "Hello world.",
            "domain": "pharma",
            "profile": {
                "archetype": "SAFETY_CRITICAL",
                "tier": "TIER_A",
                "modality": "NARRATIVE"
            }
        }

        response = client.post("/api/v1/translations/", json=payload)
        app.dependency_overrides = {}

        assert response.status_code == 201
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "processing"
        assert mock_runner.called

def test_idempotency_tmx011():
    """Verify duplicate request_id returns existing job."""
    existing_doc = MagicMock(spec=Document)
    existing_doc.id = "existing-job-id"
    existing_doc.status = DocumentStatus.TRANSLATED
    existing_doc.created_at = datetime.utcnow()
    existing_doc.client_request_id = "req-exist-1"

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = existing_doc

    from app.core.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    payload = {
        "source_language": "en",
        "target_language": "fr",
        "request_id": "req-exist-1",
        "text_content": "Ignored content.",
        "profile": {
            "archetype": "SAFETY_CRITICAL",
            "tier": "TIER_A",
            "modality": "NARRATIVE"
        }
    }

    response = client.post("/api/v1/translations/", json=payload)
    app.dependency_overrides = {}

    assert response.status_code == 201
    data = response.json()
    assert data["job_id"] == "existing-job-id"
