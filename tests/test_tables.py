import pytest
from app.services.quality_gate import QualityGateService
from app.core.defect_taxonomy import DefectCategory

def test_table_integrity_tmx035():
    """
    TMX-035: Verify Markdown Table Structure Preservation.
    """
    service = QualityGateService()

    # CASE 1: Perfect Match - use check_tables directly to avoid complexity warning
    src_ok = """| Col1 | Col2 |
|---|---|
| Val1 | Val2 |"""
    tgt_ok = """| Col1 | Col2 |
|---|---|
| Val1 | Val2 |"""
    violations = service.check_tables(src_ok, tgt_ok)
    assert len(violations) == 0

    # CASE 2: Row Drop (Missing Data Row)
    tgt_drop = """| Col1 | Col2 |
|---|---|"""
    violations = service.check_tables(src_ok, tgt_drop)
    assert len(violations) >= 1
    assert violations[0].category.value == 'TABLE_CORRUPTION'
    assert "Row Mismatch" in violations[0].message

    # CASE 3: Col Mismatch in Header
    tgt_merge = """| Col1Col2 |
|---|
| Val1 |"""
    violations = service.check_tables(src_ok, tgt_merge)
    assert len(violations) >= 1
    assert any("Mismatch" in v.message for v in violations)

if __name__ == "__main__":
    test_table_integrity_tmx035()
    print("PASS test_table_integrity_tmx035")
