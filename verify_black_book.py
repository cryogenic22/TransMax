
import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# FORCE LOCAL TEST DB
os.environ["DATABASE_URL"] = "sqlite:///./test_transmax.db"

from app.services.db_service import get_db_service

def verify():
    print("Verifying Black Book Pipeline Integration...")
    svc = get_db_service()
    
    # 1. Inspect Constraints Bundle
    print("Fetching constraints (Simulating Agent Node)...")
    constraints = svc.get_constraints(source_lang="en", target_lang="fr", query_text="side effects")
    
    print("\n--- Constraints JSON ---")
    print(json.dumps(constraints, indent=2))
    
    # 2. Assert Rule Presence
    glossary = constraints.get("glossary", [])
    found_ema = any("EMA_SAFETY" in str(item.get('reason')) for item in glossary)
    
    if found_ema:
        print("\nSUCCESS: EMA Safety Rule ('side effects' -> 'effets indésirables') found in constraint pack.")
        print("The Translation Agent will now use this rule during generation.")
    else:
        print("\nFAILURE: Seeded rules not found in constraints.")
        sys.exit(1)

if __name__ == "__main__":
    verify()
