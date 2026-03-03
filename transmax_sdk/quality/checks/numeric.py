"""GCHK-006: Ghost number check - ensures numeric values are preserved."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from transmax_sdk.types import QualityDefect, Severity


class NumericCheck:
    """Checks that all numbers in source text appear in target text."""

    name = "numeric"

    NUM_PATTERN = re.compile(r'(?<!\d)\d+(?:[.,]\d+)?(?!\d)')

    def check(
        self,
        source_text: str,
        target_text: str,
        source_lang: str,
        target_lang: str,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[QualityDefect]:
        src_nums = self.NUM_PATTERN.findall(source_text)
        if not src_nums:
            return []

        missing = []
        for num in src_nums:
            norm = re.escape(num).replace(r'\.', r'[.,]')
            if not re.search(rf'(?<!\d){norm}(?!\d)', target_text):
                missing.append(num)

        if missing:
            return [QualityDefect(
                category="NUMERIC_MISMATCH",
                severity=Severity.CRITICAL,
                message=f"[GCHK-006] Ghost Number: numbers missing in target: {missing}",
            )]
        return []
