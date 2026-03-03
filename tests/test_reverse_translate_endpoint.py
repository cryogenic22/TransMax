"""Tests for the reverse translation endpoint."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.models.database import Segment, Document


client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_init_db():
    with patch("app.main.init_db"):
        yield


def test_reverse_translate_calls_llm():
    """POST /segments/{id}/reverse should call the LLM and persist."""
    mock_seg = MagicMock(spec=Segment)
    mock_seg.id = "seg-1"
    mock_seg.document_id = "doc-1"
    mock_seg.source_text = "Take 10mg daily."
    mock_seg.translated_text = "Nehmen Sie täglich 10 mg ein."
    mock_seg.reverse_translation = None

    mock_doc = MagicMock(spec=Document)
    mock_doc.target_language = "de"
    mock_doc.source_language = "en"

    mock_db = MagicMock()
    # First query returns segment, second returns document
    mock_db.query.return_value.filter.return_value.first.side_effect = [mock_seg, mock_doc]

    mock_llm_response = MagicMock()
    mock_llm_response.content = "Take 10mg daily."

    from app.core.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    with patch("app.services.llm.get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_llm_response
        mock_get_llm.return_value = mock_llm

        response = client.post("/api/segments/seg-1/reverse")

    app.dependency_overrides = {}

    assert response.status_code == 200
    data = response.json()
    assert data["reverse_translation"] == "Take 10mg daily."
    assert data["original_source"] == "Take 10mg daily."


def test_reverse_translate_no_translation_returns_400():
    """Should return 400 if segment has no translated_text."""
    mock_seg = MagicMock(spec=Segment)
    mock_seg.id = "seg-2"
    mock_seg.translated_text = None

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_seg

    from app.core.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.post("/api/segments/seg-2/reverse")
    app.dependency_overrides = {}

    assert response.status_code == 400


def test_reverse_translate_not_found_returns_404():
    """Should return 404 if segment doesn't exist."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    from app.core.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.post("/api/segments/nonexistent/reverse")
    app.dependency_overrides = {}

    assert response.status_code == 404
