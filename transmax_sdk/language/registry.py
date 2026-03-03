"""Enhanced language pack registry with dynamic registration."""

from __future__ import annotations

from typing import Any, Dict, Optional


class LanguagePackRegistry:
    """Registry for language packs with BCP-47 fallback.

    Wraps the existing LanguagePackFactory and adds dynamic registration.
    """

    def __init__(self) -> None:
        self._custom_packs: Dict[str, Any] = {}
        self._factory = None

    def _get_factory(self):
        """Lazy-load the existing factory to avoid circular imports."""
        if self._factory is None:
            try:
                from app.services.language_packs.factory import LanguagePackFactory
                self._factory = LanguagePackFactory
            except ImportError:
                self._factory = None
        return self._factory

    def get_pack(self, lang_code: str) -> Any:
        """Get a language pack by code with BCP-47 fallback.

        Priority: custom registered packs -> existing factory packs -> None.
        """
        code = lang_code.lower()

        # 1. Custom registered packs (exact match)
        if code in self._custom_packs:
            return self._custom_packs[code]

        # 2. BCP-47 fallback on custom packs
        parts = code.split("-")
        while len(parts) > 1:
            parts.pop()
            subcode = "-".join(parts)
            if subcode in self._custom_packs:
                return self._custom_packs[subcode]

        # 3. Delegate to existing factory
        factory = self._get_factory()
        if factory:
            return factory.get_pack(lang_code)

        return None

    def register_pack(self, lang_code: str, pack: Any) -> None:
        """Register a custom language pack."""
        self._custom_packs[lang_code.lower()] = pack

    def list_codes(self) -> list[str]:
        """List all registered language codes."""
        codes = set(self._custom_packs.keys())
        factory = self._get_factory()
        if factory and hasattr(factory, "_packs"):
            codes.update(factory._packs.keys())
        return sorted(codes)
