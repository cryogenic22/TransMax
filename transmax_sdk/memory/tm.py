"""In-memory vector translation memory for headless SDK use."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.telemetry.protocol import TelemetryProtocol


class VectorTranslationMemory:
    """Translation memory with exact hash matching and optional fuzzy search.

    In headless mode (no DB), stores entries in memory.
    Exact matches use content hash for O(1) lookup.
    Fuzzy matches use simple string similarity (Jaccard) as fallback
    when no embedding provider is available.
    """

    def __init__(
        self,
        fuzzy_threshold: float = 0.85,
        telemetry: Optional[TelemetryProtocol] = None,
    ) -> None:
        self._fuzzy_threshold = fuzzy_threshold
        self._telemetry = telemetry or NoOpTelemetry()
        # Hash index: content_hash -> {target, score, metadata}
        self._exact_index: Dict[str, Dict[str, Any]] = {}
        # Full entries for fuzzy search
        self._entries: List[Dict[str, Any]] = []

    def _content_hash(self, text: str, source_lang: str, target_lang: str) -> str:
        key = f"{source_lang}:{target_lang}:{text.strip().lower()}"
        return hashlib.sha256(key.encode()).hexdigest()

    def store(
        self,
        source_text: str,
        target_text: str,
        source_lang: str,
        target_lang: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store a translation pair."""
        h = self._content_hash(source_text, source_lang, target_lang)
        entry = {
            "source_text": source_text,
            "target_text": target_text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "content_hash": h,
            "metadata": metadata or {},
        }
        self._exact_index[h] = entry
        self._entries.append(entry)

    def find_match(
        self, source_text: str, source_lang: str, target_lang: str
    ) -> Optional[Dict[str, Any]]:
        """Find best match: exact hash first, then fuzzy."""
        with self._telemetry.span("tm.find_match", {
            "source_lang": source_lang, "target_lang": target_lang,
        }):
            # 1. Exact hash match
            h = self._content_hash(source_text, source_lang, target_lang)
            if h in self._exact_index:
                entry = self._exact_index[h]
                self._telemetry.counter("transmax_tm_hits_total", labels={"type": "exact"})
                return {
                    "type": "exact",
                    "target": entry["target_text"],
                    "score": 1.0,
                }

            # 2. Fuzzy match (Jaccard similarity on word sets)
            best_score = 0.0
            best_target = None
            source_words = set(source_text.lower().split())

            for entry in self._entries:
                if entry["source_lang"] != source_lang or entry["target_lang"] != target_lang:
                    continue
                entry_words = set(entry["source_text"].lower().split())
                if not source_words or not entry_words:
                    continue

                intersection = source_words & entry_words
                union = source_words | entry_words
                similarity = len(intersection) / len(union) if union else 0.0

                if similarity > best_score:
                    best_score = similarity
                    best_target = entry["target_text"]

            if best_score >= self._fuzzy_threshold and best_target is not None:
                self._telemetry.counter("transmax_tm_hits_total", labels={"type": "fuzzy"})
                return {
                    "type": "fuzzy",
                    "target": best_target,
                    "score": best_score,
                }

            self._telemetry.counter("transmax_tm_hits_total", labels={"type": "miss"})
            return None

    def clear(self) -> None:
        """Clear all TM entries."""
        self._exact_index.clear()
        self._entries.clear()

    @property
    def size(self) -> int:
        return len(self._entries)
