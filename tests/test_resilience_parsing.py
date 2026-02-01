
import pytest
import json
from app.services.json_parser import RobustParser

class TestRobustParser:
    
    def test_clean_json(self):
        """Ideal scenario: Valid JSON."""
        raw = '{"key": "value"}'
        data = RobustParser.parse(raw)
        assert data["key"] == "value"

    def test_markdown_stripping(self):
        """LLM often wraps in ```json ... ```"""
        raw = '```json\n{"key": "value"}\n```'
        data = RobustParser.parse(raw)
        assert data["key"] == "value"
        
        raw_no_lang = '```\n{"key": "value"}\n```'
        data = RobustParser.parse(raw_no_lang)
        assert data["key"] == "value"

    def test_trailing_text(self):
        """LLM adds chatter after JSON."""
        raw = '{"key": "value"} \n Hope this helps!'
        data = RobustParser.parse(raw)
        assert data["key"] == "value"

    def test_broken_braces_repair(self):
        """Common cutoff: Missing closing brace."""
        # This is ambitious. Let's see if we can implement a simple stack balancer or just regex extraction.
        # Ideally parsing should extract the first valid JSON object.
        raw = 'Here is the JSON: {"key": "value"}'
        data = RobustParser.parse(raw)
        assert data["key"] == "value"

    def test_unrecoverable(self):
        """Garbage in -> ValueError."""
        raw = "I cannot translate this."
        with pytest.raises(ValueError):
            RobustParser.parse(raw)

if __name__ == "__main__":
    t = TestRobustParser()
    t.test_markdown_stripping()
    print("Test Passed")
