import json
import logging
from typing import Dict, Any, List
from sqlalchemy import func
from datetime import datetime, timezone

from app.services.db_service import DatabaseService
from app.models.models import TranslationJobQueue, QualityScorecard, AuditRecord, AuditLogEntry

logger = logging.getLogger(__name__)

class EvidenceService:
    """
    TMX-OPS-05: Automated Evidence Generation.
    Aggregates system metrics to prove Pilot Readiness.
    """
    
    def __init__(self):
        self.db = DatabaseService()
        
    def generate_pilot_report(self) -> Dict[str, Any]:
        session = self.db.get_session()
        try:
            # 1. Volume Metrics
            total_jobs = session.query(TranslationJobQueue).count()
            completed_jobs = session.query(TranslationJobQueue).filter(TranslationJobQueue.status == "TRANSLATED").count()
            review_jobs = session.query(TranslationJobQueue).filter(TranslationJobQueue.status == "IN_REVIEW").count()
            
            # 2. Quality Metrics (Scorecards)
            scorecards = session.query(QualityScorecard).all()
            total_scorecards = len(scorecards)
            
            total_critical = sum(s.critical_defect_count for s in scorecards)
            total_major = sum(s.major_defect_count for s in scorecards)
            avg_pass_rate = 0
            if total_scorecards > 0:
                avg_pass_rate = sum(s.gate_pass_rate for s in scorecards) / total_scorecards
                
            blocked_count = session.query(QualityScorecard).filter(QualityScorecard.status == "BLOCKED").count()
            
            # 3. Integrity Metrics (Audit Chain) — real verification
            from app.services.audit_service import AuditService
            audit_svc = AuditService(self.db)
            audit_records = session.query(AuditRecord).all()
            audit_trails = len(audit_records)
            tampered_count = 0
            for rec in audit_records:
                report = audit_svc.verify_chain_integrity(rec.audit_id)
                if not report.get("valid", True):
                    tampered_count += 1

            chain_status = "TAMPERED" if tampered_count > 0 else "VERIFIED"

            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "volume": {
                    "total_jobs": total_jobs,
                    "completed": completed_jobs,
                    "in_review": review_jobs,
                    "success_rate": (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
                },
                "quality": {
                    "scorecards_generated": total_scorecards,
                    "avg_gate_pass_rate": round(avg_pass_rate, 2),
                    "defects": {
                        "critical_total": total_critical,
                        "major_total": total_major
                    },
                    "blocked_jobs": blocked_count
                },
                "integrity": {
                    "audit_trails_active": audit_trails,
                    "tampered_chains": tampered_count,
                    "chain_status": chain_status
                },
                "readiness_verdict": "READY" if total_jobs > 0 and blocked_count == 0 and tampered_count == 0 else "CAUTION"
            }
            
        except Exception as e:
            logger.error(f"Evidence Generation Failed: {e}")
            return {"error": str(e)}
        finally:
            session.close()
