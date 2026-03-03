"""Glossary term enforcement check."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transmax_sdk.types import QualityDefect, Severity


class GlossaryCheck:
    """Ensures glossary terms are correctly applied in translation."""

    name = "glossary"

    def check(
        self,
        source_text: str,
        target_text: str,
        source_lang: str,
        target_lang: str,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[QualityDefect]:
        if not constraints:
            return []

        glossary_terms = constraints.get("glossary", [])
        defects = []

        for term in glossary_terms:
            src = term.get("source_text") or term.get("source", "")
            tgt = term.get("target_text") or term.get("target", "")
            if src and tgt and src in source_text and tgt not in target_text:
                defects.append(QualityDefect(
                    category="TERMINOLOGY",
                    severity=Severity.MAJOR,
                    message=f"Glossary term missing: '{src}' -> '{tgt}'",
                ))

        return defects
