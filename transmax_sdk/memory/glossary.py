"""In-memory glossary manager for headless SDK use."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.telemetry.protocol import TelemetryProtocol


class GlossaryManager:
    """Manages glossary terms for translation quality enforcement.

    In headless mode, stores terms in memory. Can be pre-loaded
    from a list of term dicts.
    """

    def __init__(self, telemetry: Optional[TelemetryProtocol] = None) -> None:
        self._telemetry = telemetry or NoOpTelemetry()
        self._terms: List[Dict[str, Any]] = []

    def add_term(
        self,
        source_text: str,
        target_text: str,
        source_lang: str = "en",
        target_lang: str = "",
        is_forbidden: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a glossary term."""
        self._terms.append({
            "source_text": source_text,
            "target_text": target_text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "is_forbidden": is_forbidden,
            "metadata": metadata or {},
        })

    def lookup(self, term: str, target_lang: str = "") -> List[Dict[str, Any]]:
        """Find glossary matches for a term."""
        term_lower = term.lower()
        matches = []
        for t in self._terms:
            if t["source_text"].lower() == term_lower:
                if not target_lang or t["target_lang"] == target_lang or not t["target_lang"]:
                    matches.append(t)
        return matches

    def get_terms_for_pair(self, source_lang: str, target_lang: str) -> List[Dict[str, Any]]:
        """Get all terms for a language pair."""
        return [
            t for t in self._terms
            if (t["source_lang"] == source_lang or not t["source_lang"])
            and (t["target_lang"] == target_lang or not t["target_lang"])
        ]

    def load_terms(self, terms: List[Dict[str, Any]]) -> None:
        """Bulk load terms."""
        self._terms.extend(terms)

    @property
    def size(self) -> int:
        return len(self._terms)

    def clear(self) -> None:
        self._terms.clear()
