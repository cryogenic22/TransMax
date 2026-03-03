"""Tests for the dashboard stats API endpoint."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.models.database import Document, Segment


client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_init_db():
    with patch("app.main.init_db"):
        yield


def _make_doc(**overrides):
    """Helper to build a mock Document."""
    defaults = {
        "id": "doc-1",
        "name": "test.txt",
        "status": "translated",
        "source_language": "en",
        "target_language": "fr",
        "confidence_score": 0.95,
        "updated_at": None,
    }
    defaults.update(overrides)
    doc = MagicMock(spec=Document)
    for k, v in defaults.items():
        setattr(doc, k, v)
    return doc


def test_dashboard_stats_returns_shape():
    """GET /api/dashboard/stats returns expected keys."""
    mock_db = MagicMock()
    # total_docs
    mock_db.query.return_value.scalar.return_value = 10
    # active_jobs filter
    mock_db.query.return_value.filter.return_value.scalar.return_value = 2
    mock_db.query.return_value.filter.return_value.filter.return_value.scalar.return_value = 3

    from app.core.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.get("/api/dashboard/stats")
    app.dependency_overrides = {}

    assert response.status_code == 200
    data = response.json()
    assert "total_documents" in data
    assert "active_jobs" in data
    assert "avg_quality_pct" in data
    assert "completed_24h" in data
    assert "total_segments" in data
    assert "translated_segments" in data


def test_dashboard_activity_returns_list():
    """GET /api/dashboard/activity returns a list of activity items."""
    mock_doc = _make_doc(status="in_review")

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_doc]

    from app.core.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.get("/api/dashboard/activity")
    app.dependency_overrides = {}

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["title"] == "test.txt"
    assert data[0]["priority"] == "High"


def test_dashboard_activity_empty():
    """GET /api/dashboard/activity returns empty list when no docs."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    from app.core.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.get("/api/dashboard/activity")
    app.dependency_overrides = {}

    assert response.status_code == 200
    assert response.json() == []
