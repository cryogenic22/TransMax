"""MCP tool implementations delegating to TransMaxSDK."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transmax_sdk import TransMaxSDK
from transmax_sdk.types import QualityDefect, Severity


class TransMaxTools:
    """Tool implementations for MCP server.

    Each method corresponds to an MCP tool that AI agents can call.
    """

    def __init__(self, sdk: Optional[TransMaxSDK] = None) -> None:
        self._sdk = sdk or TransMaxSDK()

    async def translate(
        self,
        text: str,
        target_lang: str,
        source_lang: str = "auto",
    ) -> Dict[str, Any]:
        """Translate text to target language.

        Returns translated text, confidence, and any defects.
        """
        result = await self._sdk.translate(
            text=text,
            target_lang=target_lang,
            source_lang=source_lang,
        )
        return {
            "translated_text": result.translated_text,
            "source_lang": result.source_lang,
            "target_lang": result.target_lang,
            "confidence": result.confidence,
            "status": result.status.value,
            "defects": [d.to_dict() for d in result.defects],
            "route_strategy": result.route_strategy.value,
        }

    def detect_language(self, text: str) -> Dict[str, Any]:
        """Detect the language of input text."""
        result = self._sdk.detect_language(text)
        return {
            "lang_code": result.lang_code,
            "confidence": result.confidence,
            "lang_name": result.lang_name,
        }

    async def quality_check(
        self,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
    ) -> Dict[str, Any]:
        """Run pharma quality gates on a translation pair."""
        defects = await self._sdk.quality_check(
            source_text=source_text,
            translated_text=translated_text,
            source_lang=source_lang,
            target_lang=target_lang,
        )

        # Determine verdict
        critical = sum(1 for d in defects if d.severity == Severity.CRITICAL)
        major = sum(1 for d in defects if d.severity == Severity.MAJOR)

        if critical > 0:
            verdict = "BLOCKED"
        elif major > 0:
            verdict = "REVIEW_REQUIRED"
        else:
            verdict = "PASS"

        return {
            "verdict": verdict,
            "defect_count": len(defects),
            "defects": [d.to_dict() for d in defects],
            "metrics": {
                "critical": critical,
                "major": major,
                "minor": sum(1 for d in defects if d.severity == Severity.MINOR),
            },
        }

    async def back_translate(
        self,
        translated_text: str,
        source_lang: str,
        target_lang: str,
    ) -> Dict[str, Any]:
        """Verify translation via back-translation."""
        result = await self._sdk.translate(
            text=translated_text,
            target_lang=source_lang,
            source_lang=target_lang,
        )
        return {
            "back_translation": result.translated_text,
            "original_lang": source_lang,
            "confidence": result.confidence,
        }

    def glossary_lookup(self, term: str, target_lang: str = "") -> Dict[str, Any]:
        """Look up a term in the glossary."""
        if self._sdk.container.has("glossary"):
            glossary = self._sdk.container.resolve("glossary")
            matches = glossary.lookup(term, target_lang)
            return {
                "term": term,
                "matches": matches,
                "match_count": len(matches),
            }
        return {"term": term, "matches": [], "match_count": 0}

    def estimate_cost(self, text: str, model: Optional[str] = None) -> Dict[str, Any]:
        """Estimate translation cost."""
        cost = self._sdk.estimate_cost(text, model)
        return {
            "estimated_cost_usd": cost,
            "model": model or self._sdk.config.default_model,
            "text_length": len(text),
        }
