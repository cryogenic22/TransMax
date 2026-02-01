import pytest
from app.services.quality_gate import QualityGateService
from app.core.policy_definitions import ViolationType

def test_table_integrity_tmx035():
    """
    TMX-035: Verify Markdown Table Structure Preservation.
    """
    service = QualityGateService()
    
    # CASE 1: Perfect Match
    src_ok = """
    Intro text.
    | Col1 | Col2 |
    |---|---|
    | Val1 | Val2 |
    Outro.
    """
    tgt_ok = """
    Intro (fr).
    | Col1 | Col2 |
    |---|---|
    | Val1 | Val2 |
    Outro (fr).
    """
    violations = service.check_segment(src_ok, tgt_ok, {}, "fr")
    assert len(violations) == 0
    
    # CASE 2: Row Drop (Missing Data Row)
    tgt_drop = """
    Intro.
    | Col1 | Col2 |
    |---|---|
    Outro.
    """
    violations = service.check_segment(src_ok, tgt_drop, {}, "fr")
    assert len(violations) >= 1
    assert violations[0]['category'] == 'TABLE_CORRUPTION'
    # Could be Row Mismatch or Table Count mismatch?
    # Both have 1 table?
    # Src: Header(2cols) + Row(2cols) = 2 rows.
    # Tgt: Header(2cols). = 1 row.
    # So Table 1 Row Mismatch: 2 vs 1.
    assert "Row Mismatch: 3 vs 2" in violations[0]['message']

    # CASE 3: Col Mismatch (Merged Cells?)
    tgt_merge = """
    | Col1 | Col2 |
    |---|---|
    | Val1MergedVal2 |
    """
    # Tgt Row 2 has `| Val |` -> 2 pipes -> 1 col.
    # Src Row 2 has 2 cols.
    # Sum(Src Cols) = 2+2=4.
    # Sum(Tgt Cols) = 2+1=3.
    # Should flag Col Mismatch.
    violations = service.check_segment(src_ok, tgt_merge, {}, "fr")
    assert len(violations) >= 1
    assert "Column Structure Mismatch" in violations[0]['message']

if __name__ == "__main__":
    test_table_integrity_tmx035()
    print("PASS test_table_integrity_tmx035")
