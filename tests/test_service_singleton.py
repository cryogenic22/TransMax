import pytest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import MagicMock, patch

def test_db_singleton():
    """Verify get_db_service returns same instance."""
    # We strip the metadata create call to avoid side effects
    with patch("app.services.db_service.Base.metadata.create_all"), \
         patch("app.services.db_service.engine"):
         
        from app.services.db_service import get_db_service
        s1 = get_db_service()
        s2 = get_db_service()
        assert s1 is s2
        assert s1._initialized == True

def test_gate_singleton():
    """Verify get_quality_gate_service returns same instance."""
    from app.services.quality_gate import get_quality_gate_service
    g1 = get_quality_gate_service()
    g2 = get_quality_gate_service()
    assert g1 is g2
    assert g1._initialized == True

if __name__ == "__main__":
    test_db_singleton()
    test_gate_singleton()
    print("Singleton Tests Passed")
