
import re
import sys

def debug_regex():
    target = "1. NAME OF THE DRUG"
    # The relaxed pattern I supposedly applied
    pattern = r'^\d+\.\s*[A-Z]' 
    
    match = re.match(pattern, target)
    print(f"Target: '{target}'")
    print(f"Pattern: '{pattern}'")
    print(f"Match Object: {match}")
    
    if match:
        print("SUCCESS: Regex matches locally.")
    else:
        print("FAILURE: Regex does not match locally.")

if __name__ == "__main__":
    debug_regex()
