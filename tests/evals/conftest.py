"""Pytest fixtures for the AI eval harness."""
from __future__ import annotations

import pytest

from app.services.quality_gate import QualityGateService


@pytest.fixture(scope="session")
def quality_gate() -> QualityGateService:
    """The deterministic quality-gate service.

    Today this is a singleton (May 2026 review C-08); v3.0 ticket TMX-3400
    refactors it. The fixture intentionally does not paper over the singleton
    so eval suites surface the same behaviour as production.
    """
    return QualityGateService()
