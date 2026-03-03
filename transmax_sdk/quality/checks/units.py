"""TMX-036: Dosage unit preservation and scientific symbol integrity."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from transmax_sdk.types import QualityDefect, Severity


class UnitsCheck:
    """Checks that dosage units and scientific symbols are preserved."""

    name = "units"

    SYMBOLS = ['°', '%', '‰', '§', '<', '>', '≤', '≥', '±']
    UNIT_PATTERN = re.compile(
        r'(\d+(?:[.,]\d+)?)\s*(mg|g|kg|mcg|µg|ml|L|mol|mmol)\b',
        re.IGNORECASE,
    )

    def check(
        self,
        source_text: str,
        target_text: str,
        source_lang: str,
        target_lang: str,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[QualityDefect]:
        defects = []

        # Symbol preservation
        for sym in self.SYMBOLS:
            if source_text.count(sym) > target_text.count(sym):
                defects.append(QualityDefect(
                    category="UNIT_MISMATCH",
                    severity=Severity.CRITICAL,
                    message=f"Symbol '{sym}' missing/reduced in target "
                            f"(source: {source_text.count(sym)}, target: {target_text.count(sym)}).",
                ))

        # Dosage unit pairs
        source_units = self.UNIT_PATTERN.findall(source_text)
        target_lower = target_text.lower()
        for val, unit in source_units:
            val_regex = re.escape(val).replace(r'\.', r'[.,]')
            full_pattern = rf"{val_regex}\s*{re.escape(unit)}"
            if not re.search(full_pattern, target_lower):
                defects.append(QualityDefect(
                    category="UNIT_MISMATCH",
                    severity=Severity.CRITICAL,
                    message=f"Dosage '{val}{unit}' not found in target.",
                ))

        return defects
