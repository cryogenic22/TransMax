import sys
import os

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from app.agents.nodes.reverse_translate import reverse_translate_node
from app.models.database import Segment

@pytest.mark.asyncio
async def test_reverse_translate_parallel_execution():
    """
    Verifies that reverse_translate_node processes segments in parallel
    and handles state updates correctly.
    """
    # 1. Setup Mock State
    segments = [
        {"segment_id": "seg_1", "translated_text": "Hello World", "source_text": "Hola Mundo"},
        {"segment_id": "seg_2", "translated_text": "Goodbye", "source_text": "Adios"},
        {"segment_id": "seg_3", "translated_text": "Computer", "source_text": "Computadora"},
    ]
    
    state = {
        "source_lang": "es",
        "target_lang": "en",
        "segments": segments,
        "job_id": "job_123"
    }

    # 2. Mock Dependencies
    mock_llm = AsyncMock()
    # Simulate a small delay to prove concurrency if we were timing it, 
    # but primarily just return unique values.
    mock_llm.ainvoke.side_effect = [
        MagicMock(content="Hola Mundo (Back)"),
        MagicMock(content="Adios (Back)"),
        MagicMock(content="Computadora (Back)")
    ]

    mock_db_instance = MagicMock()
    
    # Patch get_llm, get_db_service, and get_quality_gate_service
    with patch("app.agents.nodes.reverse_translate.get_llm", return_value=mock_llm), \
         patch("app.agents.nodes.reverse_translate.get_db_service", return_value=mock_db_instance), \
         patch("app.agents.nodes.reverse_translate.get_quality_gate_service") as MockGateService:
         
        # Mock Gate drift calculation
        mock_gate_instance = MockGateService.return_value
        mock_gate_instance.calculate_semantic_drift.return_value = 10 # Dummy score

        # 3. Execute
        result = await reverse_translate_node(state)

        # 4. Assertions
        
        # Verify LLM was called 3 times (concurrently handled inside node)
        assert mock_llm.ainvoke.call_count == 3
        
        # Verify Segments updated in-place
        assert segments[0]['reverse_translation'] == "Hola Mundo (Back)"
        assert segments[1]['reverse_translation'] == "Adios (Back)"
        
        # Verify DB Batch Update called once with all updates
        mock_db_instance.update_segments_batch.assert_called_once()
        call_args = mock_db_instance.update_segments_batch.call_args[0][0]
        assert len(call_args) == 3
        assert call_args[0]['segment_id'] == "seg_1"
        assert call_args[0]['reverse_translation'] == "Hola Mundo (Back)"

        # Verify Scorecard Update
        mock_db_instance.update_quality_scorecard_metric.assert_called_once_with(
            "job_123", {"drift_score": 10}
        )
    print("Test passed successfully!")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(test_reverse_translate_parallel_execution())
    loop.close()
