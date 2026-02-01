import sys
import os
import json
import logging

# Adjust path to Project Root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# FORCE PILOT DB (SQLite)
os.environ["DATABASE_URL"] = "sqlite:///./test_transmax.db"

from app.services.evidence_service import EvidenceService

def main():
    print("--- Generating TransMax Pilot Readiness Report ---")
    svc = EvidenceService()
    report = svc.generate_pilot_report()
    
    # Save JSON
    with open("pilot_readiness.json", "w") as f:
        json.dump(report, f, indent=2)
        
    # Generate Markdown Summary
    md = f"""# Pilot Readiness Report
**Generated**: {report['timestamp']}
**Verdict**: {report['readiness_verdict']}

## 1. System Volume
*   **Total Jobs**: {report['volume']['total_jobs']}
*   **Success Rate**: {report['volume']['success_rate']:.1f}%

## 2. Quality Assurance
*   **Gate Pass Rate (Avg)**: {report['quality']['avg_gate_pass_rate']}%
*   **Critical Defects**: {report['quality']['defects']['critical_total']}
*   **Blocked Jobs**: {report['quality']['blocked_jobs']}

## 3. Compliance
*   **Audit Trails**: {report['integrity']['audit_trails_active']}
"""
    
    with open("pilot_readiness.md", "w") as f:
        f.write(md)
        
    print("Report generated: pilot_readiness.json, pilot_readiness.md")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
