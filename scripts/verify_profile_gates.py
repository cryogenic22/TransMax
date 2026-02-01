
import sys
import os

# Ensure app can be imported
sys.path.append(os.getcwd())

from app.services.quality_gate import QualityGateService
from app.core.regulatory_profiles import get_profile

def verify_ema_date():
    print("--- Verifying EMA Date ---")
    gate = QualityGateService()
    profile_id = "EMA_SMPC_EN_GB"
    
    # 1. Check Profile Load
    prof = get_profile(profile_id)
    if not prof:
        print(f"FAILED: Profile {profile_id} not found in registry.")
        return False
        
    # FIX: Use safe access for flat structure
    date_fmt = prof.get("date_format")
    print(f"Profile Loaded: {profile_id}, Date Fmt: {date_fmt}")
    
    # 2. Check Valid Date
    text_ok = "Date of revision: 01/12/2025"
    print(f"Checking VALID: '{text_ok}'")
    v_ok = gate.check_segment("src", text_ok, {}, "en", profile_id=profile_id)
    if any(v['type'] == 'FORMATTING_ERROR' for v in v_ok):
        print("FAILED: Valid date was flagged as error.")
        return False
        
    # 3. Check Invalid Date
    text_bad = "Date: 01/30/2025" # Invalid for DD/MM/YYYY
    print(f"Checking INVALID: '{text_bad}'")
    v_bad = gate.check_segment("src", text_bad, {}, "en", profile_id=profile_id)
    
    found = False
    for v in v_bad:
        print(f"Violation Found: {v}")
        if v['type'] == 'FORMATTING_ERROR':
            found = True
            
    if not found:
        print("FAILED: Invalid date was NOT flagged.")
        return False
        
    return True

if __name__ == "__main__":
    if verify_ema_date():
        print("SUCCESS: Profile Date Gates verified.")
        sys.exit(0)
    else:
        print("FAILURE: Profile Date Gates failed.")
        sys.exit(1)
