from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import MagicMock, patch

client = TestClient(app)

@patch('app.api.endpoints.db_service')
@patch('app.api.endpoints.queue_service')
def test_structured_translation_request(mock_queue, mock_db):
    # Setup Mocks
    mock_db.create_job.return_value = "job-123"
    
    payload = {
        "blocks": [
            {"block_id": "b1", "text": "Header", "type": "header"},
            {"block_id": "b2", "text": "Paragraph content.", "type": "paragraph"}
        ],
        "source_language": "en",
        "target_language": "fr",
        "domain": "clinical"
    }
    
    response = client.post("/api/v1/translate", json=payload)
    
    assert response.status_code == 200, f"Failed: {response.text}"
    data = response.json()
    assert data['job_id'] == "job-123"
    assert data['decision'] == "PENDING"
    
    # Verify initial state construction passed to DB
    # We check the call args of db_service.create_job
    mock_db.create_job.assert_called_once()
    initial_state = mock_db.create_job.call_args[0][0]
    
    blocks = initial_state['content_blocks']
    assert len(blocks) == 2
    assert blocks[0]['content'] == "Header"
    assert blocks[1]['type'] == "paragraph"
    
    print("API Structured Input Verification Passed.")

if __name__ == "__main__":
    test_structured_translation_request()
