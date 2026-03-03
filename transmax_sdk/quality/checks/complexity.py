"""Complexity soft-mark for human review."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from transmax_sdk.types import QualityDefect, Severity


class ComplexityCheck:
    """Flags segments with LaTeX, complex tables, or code blocks for human review."""

    name = "complexity"

    def check(
        self,
        source_text: str,
        target_text: str,
        source_lang: str,
        target_lang: str,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[QualityDefect]:
        # LaTeX math
        if re.search(r'(\$|\\\[|\\\(|\\begin\{equation\})', source_text):
            return [QualityDefect(
                category="COMPLEXITY_WARNING",
                severity=Severity.MAJOR,
                message="LaTeX/Math formula detected - requires human review.",
            )]

        # Complex tables
        if source_text.count("|") > 4:
            return [QualityDefect(
                category="COMPLEXITY_WARNING",
                severity=Severity.MAJOR,
                message="Complex table structure detected - requires human review.",
            )]

        # Code blocks
        if "```" in source_text:
            return [QualityDefect(
                category="COMPLEXITY_WARNING",
                severity=Severity.MAJOR,
                message="Code block detected - requires human review.",
            )]

        return []
