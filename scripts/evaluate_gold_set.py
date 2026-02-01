
import sys
import os
import json
import uuid
import logging
from datetime import datetime

# Add project root
sys.path.append(os.getcwd())

from app.services.quality_gate import QualityGateService
from app.services.audit_service import AuditService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gold_set_eval")

# Mock Gold Set Data (In production, load from DB/File)
GOLD_SETS = {
    "smpc_v1_fr": {
        "source": "Process 10 mg daily.",
        "reference": "Traiter 10 mg par jour.",
        "expected_defects": 0,
        "family": "SmPC",
        "lang": "fr"
    },
    "warning_v1_fr": {
        "source": "Do NOT crush.",
        "reference": "Ne PAS écraser.",
        "expected_defects": 0,
        "family": "Label",
        "lang": "fr"
    }
}

def evaluate_gold_set(set_id: str):
    print(f"--- Evaluating Gold Set: {set_id} ---")
    data = GOLD_SETS.get(set_id)
    if not data:
        print("Set not found.")
        sys.exit(1)
        
    gate_svc = QualityGateService()
    
    # 1. Run Translation (Simulated for Harness)
    # In real harness, we would call the Agent Graph with frozen config.
    # Here we simulate the output to verify the HARNESS logic (comparison & reporting).
    # Simulation: Perfect Output
    actual_output = data["reference"] 
    
    # 2. Compare (Exact Match & Drift)
    print(f"Source: {data['source']}")
    print(f"Ref   : {data['reference']}")
    print(f"Actual: {actual_output}")
    
    exact_match = (actual_output == data["reference"])
    
    # Drift
    drift_score = gate_svc.calculate_semantic_drift(data["reference"], actual_output)
    
    # 3. Quality Gates
    defects = gate_svc.check_segment(data["source"], actual_output, {}, data["lang"])
    
    # 4. Generate Report
    report = {
        "set_id": set_id,
        "timestamp": datetime.utcnow().isoformat(),
        "exact_match": exact_match,
        "drift_score_vs_ref": drift_score, # Should be 100
        "defects_count": len(defects),
        "status": "PASS" if exact_match and len(defects) == data["expected_defects"] else "FAIL"
    }
    
    print("\n--- Validation Report ---")
    print(json.dumps(report, indent=2))
    
    if report["status"] == "PASS":
        print("*** VALIDATION SUCCESS ***")
    else:
        print("*** VALIDATION FAILED ***")
        sys.exit(1)

if __name__ == "__main__":
    evaluate_gold_set("smpc_v1_fr")
