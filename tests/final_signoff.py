
import subprocess
import sys
import os
import time

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

TEST_SUITE = [
    {
        "name": "Unit: Terminology Logic",
        "cmd": [sys.executable, "-m", "pytest", "tests/test_terminology.py"],
        "desc": "Verifies Mandatory and Forbidden term logic with word boundaries."
    },
    {
        "name": "Unit: Robust Parsing",
        "cmd": [sys.executable, "-m", "pytest", "tests/test_resilience_parsing.py"],
        "desc": "Verifies JSON recovery from malformed LLM output."
    },
    {
        "name": "Sprint 6: Critical Safety & Refinement",
        "cmd": [sys.executable, "tests/test_sprint6_safety.py"],
        "desc": "Verifies critical safety features and refinements."
    },
    {
        "name": "Integration: TM Bypass",
        "cmd": [sys.executable, "tests/test_tm_bypass.py"], # This is a script, not pytest (has if __main__)
        "desc": "Verifies that Exact Matches skip the LLM."
    },
    {
        "name": "Certification: Arabic Driver",
        "cmd": [sys.executable, "tests/certify_pack.py", "--pack", "ar", "--output", "testbackend/output/final_ar.txt"],
        "desc": "Verifies RTL, Hindi Digits, and Negation checks for Arabic."
    },
    {
        "name": "Certification: Japanese Driver",
        "cmd": [sys.executable, "tests/certify_pack.py", "--pack", "ja", "--output", "testbackend/output/final_ja.txt"],
        "desc": "Verifies Variants and Punctuation checks for Japanese."
    },
    {
        "name": "E2E: Forbidden Terms",
        "cmd": [sys.executable, "tests/test_terminology_e2e.py"],
        "desc": "Verifies full pipeline blocking of forbidden terms with Real LLM."
    }
]

def run_suite():
    print(f"{Colors.HEADER}=================================================={Colors.ENDC}")
    print(f"{Colors.HEADER}   REGULATORY SIGN-OFF SUITE (GOLDEN MASTER)      {Colors.ENDC}")
    print(f"{Colors.HEADER}=================================================={Colors.ENDC}\n")
    
    results = []
    
    start_total = time.time()
    
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd() # Ensure root is in path for module imports

    for test in TEST_SUITE:
        print(f"{Colors.BOLD}Running: {test['name']}...{Colors.ENDC}")
        print(f"  > Description: {test['desc']}")
        
        start = time.time()
        try:
            # Capture output
            result = subprocess.run(test['cmd'], capture_output=True, text=True, env=env)
            duration = time.time() - start
            
            if result.returncode == 0:
                print(f"  {Colors.OKGREEN}PASSED{Colors.ENDC} ({duration:.2f}s)")
                results.append({"name": test['name'], "status": "PASS", "duration": duration})
            else:
                print(f"  {Colors.FAIL}FAILED{Colors.ENDC} ({duration:.2f}s)")
                print(f"  {Colors.FAIL}Error Output:\n{result.stderr}{Colors.ENDC}")
                print(f"  {Colors.FAIL}Std Output:\n{result.stdout}{Colors.ENDC}")
                results.append({"name": test['name'], "status": "FAIL", "duration": duration})
                
        except Exception as e:
            print(f"  {Colors.FAIL}CRASHED: {e}{Colors.ENDC}")
            results.append({"name": test['name'], "status": "CRASH", "duration": 0})
            
        print("-" * 50)

    end_total = time.time()
    
    print(f"\n{Colors.HEADER}=== FINAL SUMMARY ==={Colors.ENDC}")
    all_passed = True
    for res in results:
        color = Colors.OKGREEN if res['status'] == "PASS" else Colors.FAIL
        print(f"{color}[{res['status']}] {res['name']}{Colors.ENDC}")
        if res['status'] != "PASS":
            all_passed = False
            
    if all_passed:
        print(f"\n{Colors.OKGREEN}✅ REGULATORY SIGN-OFF SUCCESSFUL{Colors.ENDC}")
        sys.exit(0)
    else:
        print(f"\n{Colors.FAIL}❌ SIGN-OFF FAILED{Colors.ENDC}")
        sys.exit(1)

if __name__ == "__main__":
    run_suite()
