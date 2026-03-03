"""TMX-034: Placeholder preservation check."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Optional

from transmax_sdk.types import QualityDefect, Severity


class PlaceholdersCheck:
    """Ensures {{var}} and [#] placeholders are preserved exactly."""

    name = "placeholders"

    PATTERN = re.compile(r'(\{\{.*?\}\}|\[\d+\])')

    def check(
        self,
        source_text: str,
        target_text: str,
        source_lang: str,
        target_lang: str,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[QualityDefect]:
        src_phs = self.PATTERN.findall(source_text)
        if not src_phs:
            return []

        tgt_phs = self.PATTERN.findall(target_text)
        s_count = Counter(src_phs)
        t_count = Counter(tgt_phs)

        defects = []

        # Missing placeholders
        missing = s_count - t_count
        if missing:
            defects.append(QualityDefect(
                category="FORMATTING",
                severity=Severity.CRITICAL,
                message=f"Placeholders missing: {list(missing.elements())}",
            ))

        # Hallucinated placeholders
        added = t_count - s_count
        if added:
            defects.append(QualityDefect(
                category="FORMATTING",
                severity=Severity.MAJOR,
                message=f"Placeholders hallucinated: {list(added.elements())}",
            ))

        return defects
