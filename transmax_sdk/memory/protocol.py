"""Translation memory and glossary protocols."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class TranslationMemoryProtocol(Protocol):
    """Interface for translation memory implementations."""

    def find_match(
        self, source_text: str, source_lang: str, target_lang: str
    ) -> Optional[Dict[str, Any]]:
        """Find the best TM match. Returns {type, target, score} or None."""
        ...

    def store(
        self,
        source_text: str,
        target_text: str,
        source_lang: str,
        target_lang: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store a translation pair in TM."""
        ...


@runtime_checkable
class GlossaryManagerProtocol(Protocol):
    """Interface for glossary management."""

    def lookup(self, term: str, target_lang: str) -> List[Dict[str, Any]]:
        """Look up glossary matches for a term."""
        ...

    def add_term(
        self, source_text: str, target_text: str, source_lang: str, target_lang: str
    ) -> None:
        """Add a term to the glossary."""
        ...
