import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import MagicMock, patch
from app.services.resilience import ResilienceService
from app.models.models import DeadLetterQueue

def test_dlq_persistence():
    job_id = "test_job_123"
    error_code = "TEST_EXPLOSION"
    error_trace = "Traceback: Line 1: Boom"
    payload = {"foo": "bar"}

    mock_db_svc = MagicMock()
    mock_session = MagicMock()
    mock_db_svc.get_session.return_value = mock_session

    with patch("app.services.db_service.get_db_service", return_value=mock_db_svc):
        ResilienceService.move_to_dlq(job_id, error_code, error_trace, payload)

        assert mock_session.add.called
        args = mock_session.add.call_args[0][0]
        assert isinstance(args, DeadLetterQueue)
        assert args.job_id == job_id
        assert args.error_code == error_code
        assert args.payload_snapshot == payload
        mock_session.commit.assert_called_once()
        print("DLQ Test Passed")

if __name__ == "__main__":
    test_dlq_persistence()
