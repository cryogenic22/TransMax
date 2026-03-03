"""Language capability matrix: per-provider confidence scores for language pairs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class LanguageCapability:
    """Translation capability of a provider for a specific language pair."""

    provider: str
    source_lang: str
    target_lang: str
    confidence: float  # 0.0 - 1.0
    cost_tier: int  # 1 (cheapest) to 3 (most expensive)
    default_model: str


class CapabilityMatrix:
    """Lookup table mapping (provider, src, tgt) -> LanguageCapability."""

    def __init__(self, capabilities: List[LanguageCapability]) -> None:
        self._by_key: Dict[Tuple[str, str, str], LanguageCapability] = {}
        self._by_pair: Dict[Tuple[str, str], List[LanguageCapability]] = {}
        self._languages: Set[str] = set()

        for cap in capabilities:
            key = (cap.provider, cap.source_lang, cap.target_lang)
            self._by_key[key] = cap

            pair = (cap.source_lang, cap.target_lang)
            self._by_pair.setdefault(pair, []).append(cap)

            self._languages.add(cap.source_lang)
            self._languages.add(cap.target_lang)

    def get(
        self, provider: str, source_lang: str, target_lang: str
    ) -> Optional[LanguageCapability]:
        """Exact lookup for a provider + language pair."""
        return self._by_key.get((provider, source_lang, target_lang))

    def get_best_for_pair(
        self,
        source_lang: str,
        target_lang: str,
        available_providers: Optional[Set[str]] = None,
    ) -> Optional[LanguageCapability]:
        """Return the highest-confidence capability for a language pair."""
        candidates = self._by_pair.get((source_lang, target_lang), [])
        if available_providers is not None:
            candidates = [c for c in candidates if c.provider in available_providers]
        if not candidates:
            return None
        return max(candidates, key=lambda c: c.confidence)

    def confidence_for_pair(
        self,
        source_lang: str,
        target_lang: str,
        available_providers: Optional[Set[str]] = None,
    ) -> float:
        """Return max confidence across available providers for a pair."""
        best = self.get_best_for_pair(source_lang, target_lang, available_providers)
        return best.confidence if best else 0.0

    def supported_languages(self) -> Set[str]:
        """Return all language codes present in the matrix."""
        return set(self._languages)

    def providers_for_pair(
        self, source_lang: str, target_lang: str
    ) -> List[LanguageCapability]:
        """Return all capabilities for a language pair, sorted by confidence desc."""
        caps = self._by_pair.get((source_lang, target_lang), [])
        return sorted(caps, key=lambda c: c.confidence, reverse=True)


def _build_default_matrix() -> CapabilityMatrix:
    """Build the hardcoded default capability matrix."""
    caps: List[LanguageCapability] = []

    # --- OpenAI capabilities ---
    openai_european = [
        ("en", "fr", 0.95), ("fr", "en", 0.95),
        ("en", "de", 0.94), ("de", "en", 0.94),
        ("en", "es", 0.95), ("es", "en", 0.95),
        ("en", "pt", 0.93), ("pt", "en", 0.93),
        ("en", "it", 0.93), ("it", "en", 0.93),
        ("en", "nl", 0.92), ("nl", "en", 0.92),
        ("en", "pl", 0.90), ("pl", "en", 0.90),
        ("en", "ru", 0.91), ("ru", "en", 0.91),
        ("en", "sv", 0.92), ("sv", "en", 0.92),
        ("en", "da", 0.91), ("da", "en", 0.91),
        ("fr", "de", 0.92), ("de", "fr", 0.92),
        ("es", "pt", 0.93), ("pt", "es", 0.93),
        ("fr", "es", 0.92), ("es", "fr", 0.92),
        ("fr", "it", 0.91), ("it", "fr", 0.91),
    ]
    openai_cjk = [
        ("en", "ja", 0.90), ("ja", "en", 0.90),
        ("en", "zh", 0.89), ("zh", "en", 0.89),
        ("en", "ko", 0.88), ("ko", "en", 0.88),
    ]
    openai_other = [
        ("en", "ar", 0.88), ("ar", "en", 0.88),
        ("en", "hi", 0.85), ("hi", "en", 0.85),
        ("en", "th", 0.84), ("th", "en", 0.84),
        ("en", "vi", 0.84), ("vi", "en", 0.84),
        ("en", "tr", 0.87), ("tr", "en", 0.87),
        ("en", "id", 0.86), ("id", "en", 0.86),
    ]
    for src, tgt, conf in openai_european + openai_cjk + openai_other:
        caps.append(LanguageCapability("openai", src, tgt, conf, 2, "gpt-4o"))

    # --- Anthropic capabilities ---
    anthropic_european = [
        ("en", "fr", 0.94), ("fr", "en", 0.94),
        ("en", "de", 0.93), ("de", "en", 0.93),
        ("en", "es", 0.94), ("es", "en", 0.94),
        ("en", "pt", 0.92), ("pt", "en", 0.92),
        ("en", "it", 0.92), ("it", "en", 0.92),
        ("en", "nl", 0.91), ("nl", "en", 0.91),
        ("en", "pl", 0.89), ("pl", "en", 0.89),
        ("en", "ru", 0.90), ("ru", "en", 0.90),
        ("en", "sv", 0.91), ("sv", "en", 0.91),
        ("en", "da", 0.90), ("da", "en", 0.90),
        ("fr", "de", 0.91), ("de", "fr", 0.91),
        ("es", "pt", 0.92), ("pt", "es", 0.92),
        ("fr", "es", 0.91), ("es", "fr", 0.91),
        ("fr", "it", 0.90), ("it", "fr", 0.90),
    ]
    anthropic_cjk = [
        ("en", "ja", 0.88), ("ja", "en", 0.88),
        ("en", "zh", 0.87), ("zh", "en", 0.87),
        ("en", "ko", 0.86), ("ko", "en", 0.86),
    ]
    anthropic_other = [
        ("en", "ar", 0.87), ("ar", "en", 0.87),
        ("en", "hi", 0.84), ("hi", "en", 0.84),
        ("en", "th", 0.82), ("th", "en", 0.82),
        ("en", "vi", 0.83), ("vi", "en", 0.83),
        ("en", "tr", 0.86), ("tr", "en", 0.86),
        ("en", "id", 0.85), ("id", "en", 0.85),
    ]
    for src, tgt, conf in anthropic_european + anthropic_cjk + anthropic_other:
        caps.append(LanguageCapability("anthropic", src, tgt, conf, 2, "claude-sonnet-4-20250514"))

    # --- Gemini capabilities ---
    gemini_european = [
        ("en", "fr", 0.92), ("fr", "en", 0.92),
        ("en", "de", 0.91), ("de", "en", 0.91),
        ("en", "es", 0.92), ("es", "en", 0.92),
        ("en", "pt", 0.90), ("pt", "en", 0.90),
        ("en", "it", 0.90), ("it", "en", 0.90),
        ("en", "nl", 0.89), ("nl", "en", 0.89),
        ("en", "pl", 0.88), ("pl", "en", 0.88),
        ("en", "ru", 0.89), ("ru", "en", 0.89),
        ("en", "sv", 0.89), ("sv", "en", 0.89),
        ("en", "da", 0.88), ("da", "en", 0.88),
        ("fr", "de", 0.89), ("de", "fr", 0.89),
        ("es", "pt", 0.90), ("pt", "es", 0.90),
        ("fr", "es", 0.89), ("es", "fr", 0.89),
        ("fr", "it", 0.88), ("it", "fr", 0.88),
    ]
    gemini_cjk = [
        ("en", "ja", 0.91), ("ja", "en", 0.91),
        ("en", "zh", 0.90), ("zh", "en", 0.90),
        ("en", "ko", 0.89), ("ko", "en", 0.89),
    ]
    gemini_indic = [
        ("en", "hi", 0.93), ("hi", "en", 0.93),
        ("en", "th", 0.90), ("th", "en", 0.90),
        ("en", "vi", 0.90), ("vi", "en", 0.90),
        ("en", "id", 0.91), ("id", "en", 0.91),
    ]
    gemini_other = [
        ("en", "ar", 0.89), ("ar", "en", 0.89),
        ("en", "tr", 0.88), ("tr", "en", 0.88),
    ]
    for src, tgt, conf in gemini_european + gemini_cjk + gemini_indic + gemini_other:
        caps.append(LanguageCapability("gemini", src, tgt, conf, 1, "gemini-2.0-flash"))

    return CapabilityMatrix(caps)


DEFAULT_CAPABILITY_MATRIX = _build_default_matrix()
