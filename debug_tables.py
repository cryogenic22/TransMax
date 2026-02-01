
from typing import List, Dict, Any
import re
from dataclasses import dataclass

@dataclass
class Defect:
    category: str
    message: str

class DefectCategory:
    TABLE_CORRUPTION = "TABLE_CORRUPTION"

class MockService:
    def _create_defect(self, category, message):
         return Defect(category, message)

    def check_tables(self, source_text: str, target_text: str) -> List[Defect]:
        """
        TMX-035: Markdown Table Structure Preservation.
        """
        def count_tables(text):
            lines = text.strip().split('\n')
            count = 0
            in_table = False
            for line in lines:
                if line.strip().startswith('|'):
                    if not in_table:
                        count += 1
                        in_table = True
                else:
                    in_table = False
            return count

        def get_table_structure(text):
            structures = []
            lines = text.strip().split('\n')
            current_rows = 0
            current_cols = []
            in_table = False
            
            for line in lines:
                if line.strip().startswith('|'):
                    in_table = True
                    current_rows += 1
                    cols = line.count('|') - 1
                    if cols > 0:
                        current_cols.append(cols)
                else:
                    if in_table:
                        structures.append({'rows': current_rows, 'cols': current_cols})
                        current_rows = 0
                        current_cols = []
                        in_table = False
            
            if in_table:
                 structures.append({'rows': current_rows, 'cols': current_cols})
            return structures

        defects = []
        
        # 1. Table Count
        src_tables = count_tables(source_text)
        tgt_tables = count_tables(target_text)
        print(f"DEBUG: src_tables={src_tables} tgt_tables={tgt_tables}")
        
        if src_tables != tgt_tables:
            defects.append(self._create_defect(
                DefectCategory.TABLE_CORRUPTION,
                f"Table count mismatch: Source has {src_tables}, Target has {tgt_tables}."
            ))
            return defects 
            
        if src_tables == 0:
            return []

        # 2. Structure Detail
        src_struct = get_table_structure(source_text)
        tgt_struct = get_table_structure(target_text)
        print(f"DEBUG: src={src_struct} tgt={tgt_struct}")
        
        for i, (s, t) in enumerate(zip(src_struct, tgt_struct)):
            if s['rows'] != t['rows']:
                 defects.append(self._create_defect(
                    DefectCategory.TABLE_CORRUPTION,
                    f"Table {i+1} Row Mismatch: {s['rows']} vs {t['rows']}."
                ))
            elif s['cols'] and t['cols'] and s['cols'][0] != t['cols'][0]:
                 defects.append(self._create_defect(
                    DefectCategory.TABLE_CORRUPTION,
                    f"Table {i+1} Column Structure Mismatch (Header): {s['cols'][0]} vs {t['cols'][0]}."
                ))
                
        return defects

if __name__ == "__main__":
    src_ok = """
    Intro text.
    | Col1 | Col2 |
    |---|---|
    | Val1 | Val2 |
    Outro.
    """
    tgt_drop = """
    Intro.
    | Col1 | Col2 |
    |---|---|
    Outro.
    """
    
    svc = MockService()
    print("Checking...")
    defects = svc.check_tables(src_ok, tgt_drop)
    print(f"Defects: {defects}")
    assert len(defects) >= 1
    print("Logic Verified")
