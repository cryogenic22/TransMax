"""TMX-035: Markdown table structure preservation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transmax_sdk.types import QualityDefect, Severity


class TablesCheck:
    """Verifies markdown table structure is preserved in translation."""

    name = "tables"

    def check(
        self,
        source_text: str,
        target_text: str,
        source_lang: str,
        target_lang: str,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[QualityDefect]:
        src_tables = self._count_tables(source_text)
        tgt_tables = self._count_tables(target_text)

        defects = []

        if src_tables != tgt_tables:
            defects.append(QualityDefect(
                category="TABLE_CORRUPTION",
                severity=Severity.CRITICAL,
                message=f"Table count mismatch: source={src_tables}, target={tgt_tables}.",
            ))
            return defects

        if src_tables == 0:
            return []

        src_struct = self._get_structure(source_text)
        tgt_struct = self._get_structure(target_text)

        for i, (s, t) in enumerate(zip(src_struct, tgt_struct)):
            if s["rows"] != t["rows"]:
                defects.append(QualityDefect(
                    category="TABLE_CORRUPTION",
                    severity=Severity.CRITICAL,
                    message=f"Table {i+1} row mismatch: {s['rows']} vs {t['rows']}.",
                ))
            elif s["cols"] and t["cols"] and s["cols"][0] != t["cols"][0]:
                defects.append(QualityDefect(
                    category="TABLE_CORRUPTION",
                    severity=Severity.CRITICAL,
                    message=f"Table {i+1} column mismatch: {s['cols'][0]} vs {t['cols'][0]}.",
                ))

        return defects

    @staticmethod
    def _count_tables(text: str) -> int:
        count, in_table = 0, False
        for line in text.strip().split("\n"):
            if line.strip().startswith("|"):
                if not in_table:
                    count += 1
                    in_table = True
            else:
                in_table = False
        return count

    @staticmethod
    def _get_structure(text: str) -> List[Dict[str, Any]]:
        structures = []
        rows, cols = 0, []
        in_table = False
        for line in text.strip().split("\n"):
            if line.strip().startswith("|"):
                in_table = True
                rows += 1
                c = line.count("|") - 1
                if c > 0:
                    cols.append(c)
            else:
                if in_table:
                    structures.append({"rows": rows, "cols": cols})
                    rows, cols = 0, []
                    in_table = False
        if in_table:
            structures.append({"rows": rows, "cols": cols})
        return structures
