"""
TMX-MQM-SHADOW-REPORT — summarise the MQM engine shadow run for the cutover gate.

Read-only. Reads the `MQM_SHADOW_SCORE` events the gate node emits to the v2
audit chain (TMX-MQM-5a-emit) and reports how the pure MQM engine compares to
the legacy deterministic verdict over real traffic: block-agreement rate and
the CQS distribution. This is the evidence reviewed BEFORE flipping
`mqm_engine_enabled` (the phase-b cutover, ADR-0007 / review condition 4).

Usage:
    python -m scripts.mqm_shadow_report [--json]

It scans across tenants (forensic-admin read; the documented
`include_other_tenants` opt-out) so a single report covers the pilot.
"""
from __future__ import annotations

import json
import sys
from statistics import mean
from typing import Any, Dict, List


def collect_shadow_rows() -> List[Dict[str, Any]]:
    from app.core.database import SessionLocal
    from app.models.audit_v2 import AuditEventV2

    session = SessionLocal()
    try:
        q = (
            session.query(AuditEventV2)
            .filter(AuditEventV2.event_type == "MQM_SHADOW_SCORE")
            .execution_options(include_other_tenants=True)  # admin/forensic scan
        )
        return [r.payload or {} for r in q.all()]
    finally:
        session.close()


def summarise(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(rows)
    if total == 0:
        return {"total": 0, "note": "no MQM_SHADOW_SCORE events yet - run traffic with mqm_shadow_enabled on"}
    agree = sum(1 for r in rows if r.get("block_agreement"))
    cqs = [r["mqm"]["cqs"] for r in rows if isinstance(r.get("mqm"), dict) and r["mqm"].get("cqs") is not None]
    critical = sum(1 for r in rows if isinstance(r.get("mqm"), dict) and r["mqm"].get("critical_auto_fail"))
    insufficient = sum(1 for r in rows if isinstance(r.get("mqm"), dict) and r["mqm"].get("insufficient_sample"))
    return {
        "total": total,
        "block_agreement_rate": round(agree / total, 3),
        "disagreements": total - agree,
        "mqm_critical_auto_fail": critical,
        "mqm_insufficient_sample": insufficient,
        "cqs_min": round(min(cqs), 2) if cqs else None,
        "cqs_mean": round(mean(cqs), 2) if cqs else None,
        "cqs_max": round(max(cqs), 2) if cqs else None,
    }


def main() -> int:
    rows = collect_shadow_rows()
    summary = summarise(rows)
    if "--json" in sys.argv:
        print(json.dumps(summary, indent=2))
    else:
        print("MQM engine shadow report (legacy vs MQM, for the phase-b cutover gate)")
        print("-" * 68)
        for k, v in summary.items():
            print(f"  {k:28} {v}")
        if summary.get("total"):
            print("-" * 68)
            print("  Review block_agreement_rate + the disagreements before flipping")
            print("  mqm_engine_enabled (ADR-0007 / review condition 4).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
