import pytest
from unittest.mock import MagicMock, patch
from app.services.db_service import DatabaseService

@patch('app.services.db_service.settings')
def test_vector_search_logic(mock_settings):
    """Test get_constraints with mocked embeddings and DB."""
    mock_settings.openai_api_key = "fake_key"

    mock_db = MagicMock()
    mock_query = mock_db.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_order = mock_filter.order_by.return_value
    mock_limit = mock_order.limit.return_value
    mock_limit.all.return_value = []
    # Also mock filter_by for glossary queries
    mock_query.filter_by.return_value.all.return_value = []

    mock_embed_instance = MagicMock()
    mock_embed_instance.embed_query.return_value = [0.1] * 1536

    service = DatabaseService()

    with patch.object(service, 'get_session', return_value=mock_db):
        with patch('langchain_openai.OpenAIEmbeddings', return_value=mock_embed_instance) as mock_embeddings:
            constraints = service.get_constraints("en", "es", query_text="hello world")

    assert "tm_matches" in constraints
    print("Vector search logic verified successfully.")

if __name__ == "__main__":
    try:
        test_vector_search_logic()
    except Exception as e:
        print(f"Test failed: {e}")
        exit(1)
