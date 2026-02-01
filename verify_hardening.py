import sys
import os
# Add project root to path
sys.path.append(os.getcwd())

from app.services.quality_gate import QualityGateService
from app.core.defect_taxonomy import DefectCategory, DefectSeverity

def test_hardening():
    service = QualityGateService()
    print("--- Verifying Quality Gate Hardening ---")
    
    # 1. Test Complexity Soft-Mark
    print("\n1. Testing Complexity Check (LaTeX):")
    source_latex = "The area is calculated as $A = \pi r^2$."
    defects = service.check_segment(source_latex, "Die Fläche ist...", {}, "de")
    # defects is list of dicts
    complexity_defect = next((d for d in defects if d['category'] == DefectCategory.COMPLEXITY_WARNING.value), None)
    
    if complexity_defect:
        print(f"✅ Complexity Detected: {complexity_defect['message']}")
        assert complexity_defect['severity'] == DefectSeverity.MAJOR.value
    else:
        print("❌ FAILED: Latex not detected.")
        
    print("\n2. Testing Complexity Check (Complex Table):")
    source_table = "| Col 1 | Col 2 | Col 3 | Col 4 | Col 5 |"
    defects = service.check_segment(source_table, "| Col 1 |", {}, "de")
    complexity_defect = next((d for d in defects if d['category'] == DefectCategory.COMPLEXITY_WARNING.value), None)
    
    if complexity_defect:
        print(f"✅ Complex Table Detected: {complexity_defect['message']}")
    else:
        print("❌ FAILED: Complex table not detected.")

    # 2. Test Privacy Shield Fail-Safe
    print("\n3. Testing PII Fail-Safe (Raw Email in Target):")
    source_text = "Contact me."
    target_text = "Contact john.doe@example.com immediately." # Leaked PII
    
    defects = service.check_segment(source_text, target_text, {}, "de")
    pii_defect = next((d for d in defects if d['category'] == DefectCategory.PII_LEAK.value), None)
    
    if pii_defect:
        print(f"✅ PII Leak Detected: {pii_defect['message']}")
        assert "EMAIL" in pii_defect['message'] or "Privacy Shield" in pii_defect['message']
    else:
        print("❌ FAILED: PII Leak not detected.")

    print("\nVerification Complete.")

if __name__ == "__main__":
    test_hardening()
