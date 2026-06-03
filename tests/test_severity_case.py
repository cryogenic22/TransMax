"""TMX-QG-SEVCASE — case-insensitive critical-severity detection.

Reproduces the latent defect: the quality gate emits uppercase "CRITICAL", but
call sites compared against lowercase 'critical' and so never matched, leaving
auto-block (engine) and refine-exclusion (graph) broken for critical defects.
"""
from __future__ import annotations

import pytest

from app.core.defect_taxonomy import DefectSeverity, is_critical


@pytest.mark.parametrize("value,expected", [
    ("CRITICAL", True),          # canonical gate output — was the broken case
    ("critical", True),          # legacy lowercase (db_service)
    ("Critical", True),
    (DefectSeverity.CRITICAL, True),  # enum member
    ("MAJOR", False),
    ("major", False),
    (DefectSeverity.MINOR, False),
    (None, False),
    ("", False),
])
def test_is_critical(value, expected):
    assert is_critical(value) is expected


def test_uppercase_critical_violation_is_detected():
    """The exact failure mode: a violation carrying the gate's real uppercase
    severity must be recognised as critical (the old `== 'critical'` returned
    False here)."""
    violation = {"segment_id": "1", "severity": DefectSeverity.CRITICAL.value, "message": "x"}
    assert is_critical(violation["severity"]) is True
    # The legacy lowercase comparison this replaces:
    assert (violation["severity"] == "critical") is False  # documents why it was broken
