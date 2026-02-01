
import sys
import os

# Ensure app can be imported
sys.path.append(os.getcwd())

from app.services.quality_gate import QualityGateService
from app.core.regulatory_profiles import get_profile

def verify_structure_gates():
    print("--- Verifying Structure Gates ---")
    gate = QualityGateService()
    
    # ----------------------------------------------------
    # TEST 1: EMA PROFILE (Strict)
    # ----------------------------------------------------
    profile_id = "EMA_SMPC_EN_GB"
    print(f"\n[Testing {profile_id}]")
    prof = get_profile(profile_id)
    if not prof:
        print("FAILED: Profile not found")
        return False

    # A. Valid Header
    text_ok = "1. NAME OF THE MEDICINAL PRODUCT"
    v_ok = gate.check_segment("source", text_ok, {}, "en", profile_id=profile_id)
    if any(v['type'] == 'STRUCTURE_ERROR' for v in v_ok):
        print(f"FAILED: Valid header '{text_ok}' flagged as error: {v_ok}")
        return False
    else:
        print(f"PASS: '{text_ok}' accepted.")

    # B. Invalid Header
    text_bad = "1. NAME OF THE DRUG"
    v_bad = gate.check_segment("source", text_bad, {}, "en", profile_id=profile_id)
    found = any(v['type'] == 'STRUCTURE_ERROR' for v in v_bad)
    if not found:
        # Debug why
        import re
        pat = r'^\d+\.\s*[A-Z\s\(\)]+$'
        is_match = bool(re.match(pat, text_bad))
        print(f"FAILED: Invalid header '{text_bad}' NOT flagged. Regex Match: {is_match}")
        return False
    else:
        print(f"PASS: '{text_bad}' correctly flagged.")

    # C. Normal Text (Should be ignored)
    text_normal = "This product contains 500mg paracetamol."
    v_normal = gate.check_segment("source", text_normal, {}, "en", profile_id=profile_id)
    if any(v['type'] == 'STRUCTURE_ERROR' for v in v_normal):
        print(f"FAILED: Normal text '{text_normal}' flagged as header error: {v_normal}")
        return False
    else:
        print(f"PASS: Normal text ignored.")

    # ----------------------------------------------------
    # TEST 2: MARKETING PROFILE (Flexible)
    # ----------------------------------------------------
    profile_id = "MARKETING_GLOBAL_EN"
    print(f"\n[Testing {profile_id}]")

    # D. "Invalid" Header (should be allowed)
    text_loose = "1. NAME OF THE DRUG"
    v_loose = gate.check_segment("source", text_loose, {}, "en", profile_id=profile_id)
    if any(v['type'] == 'STRUCTURE_ERROR' for v in v_loose):
        print(f"FAILED: '{text_loose}' flagged in Marketing Mode!")
        return False
    else:
        print(f"PASS: '{text_loose}' allowed in Marketing Mode.")

    return True

if __name__ == "__main__":
    if verify_structure_gates():
        print("\nSUCCESS: All Structure Gates Verified.")
        sys.exit(0)
    else:
        print("\nFAILURE: Structure Gates Failed.")
        sys.exit(1)
