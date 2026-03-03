"""PII leak detection in translated text."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from transmax_sdk.types import QualityDefect, Severity

# Default PII patterns (same as app/services/pii_service.py)
PII_PATTERNS = {
    "EMAIL": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    "PHONE": r'\b(?:\+?1[-. ]?)?\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})\b',
    "SSN": r'\b\d{3}-\d{2}-\d{4}\b',
    "IPV4": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
    "CREDIT_CARD": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
}


class PIICheck:
    """Detects potential PII leakage in target text."""

    name = "pii"

    def __init__(self, patterns: Optional[Dict[str, str]] = None):
        self._patterns = patterns or PII_PATTERNS

    def check(
        self,
        source_text: str,
        target_text: str,
        source_lang: str,
        target_lang: str,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[QualityDefect]:
        defects = []

        # Check for unresolved PII tokens
        if "[[PII" in target_text or "<EMAIL" in target_text or "<PHONE" in target_text:
            defects.append(QualityDefect(
                category="PII_LEAK",
                severity=Severity.MAJOR,
                message="Unresolved PII redaction token found in target.",
            ))

        # Check for raw PII patterns
        leaked_types = set()
        for pii_type, pattern in self._patterns.items():
            if re.search(pattern, target_text):
                leaked_types.add(pii_type)

        if leaked_types:
            defects.append(QualityDefect(
                category="PII_LEAK",
                severity=Severity.MAJOR,
                message=f"Potential PII leakage in target: {leaked_types}",
            ))

        return defects
