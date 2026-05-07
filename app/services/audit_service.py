
import json
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.database import DEFAULT_ORG_ID
from app.models.models import AuditRecord, AuditLogEntry, JobConfigSnapshot
from app.services.db_service import DatabaseService

logger = logging.getLogger(__name__)

class AuditService:
    """
    TMX-020: Secure Audit Service.
    Manages the 'Black Box' recording of all agentic actions.
    Enforces hash-chaining (blockchain-style) for tamper evidence.
    """
    
    def __init__(self, db_service: DatabaseService = None):
        self.db_service = db_service or DatabaseService()

    def create_audit_trail(self, job_id: str) -> str:
        """
        Initializes a new Audit Trail (AuditRecord) for a job.
        Returns audit_id.
        """
        session = self.db_service.get_session()
        try:
            audit_id = str(uuid.uuid4())
            record = AuditRecord(
                audit_id=audit_id,
                # TMX-3012 will replace with session-context injection (A3-sensitive on audit).
                organization_id=DEFAULT_ORG_ID,
                job_id=job_id,
                created_at=datetime.now(timezone.utc)
            )
            session.add(record)
            session.commit()
            logger.info(f"Initialized Audit Trail {audit_id} for Job {job_id}")
            return audit_id
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create audit trail: {e}")
            raise e
        finally:
            session.close()

    def log_event(self, audit_id: str, event_type: str, payload: Dict[str, Any]) -> str:
        """
        Appends an event to the tamper-evident log.
        Calculates SHA256(previous_hash + payload) to lock the chain.
        Returns entry_id.
        """
        session = self.db_service.get_session()
        try:
            # 1. Fetch the last entry to get previous_hash and sequence
            last_entry = session.query(AuditLogEntry)\
                .filter(AuditLogEntry.audit_id == audit_id)\
                .order_by(desc(AuditLogEntry.sequence_index))\
                .first()
            
            sequence_index = 0
            previous_hash = "GENESIS_HASH" # Seed for the first entry
            
            if last_entry:
                sequence_index = last_entry.sequence_index + 1
                previous_hash = last_entry.entry_hash
            
            # 2. Canonicalize Payload (Sort keys for deterministic hashing)
            payload_json = json.dumps(payload, sort_keys=True)
            
            # 3. Calculate New Hash
            # H = SHA256( previous_hash + payload_string )
            hash_input = f"{previous_hash}{payload_json}"
            entry_hash = hashlib.sha256(hash_input.encode()).hexdigest()
            
            # 4. Create Entry
            entry_id = str(uuid.uuid4())
            new_entry = AuditLogEntry(
                entry_id=entry_id,
                # TMX-3012 will replace with session-context injection.
                organization_id=DEFAULT_ORG_ID,
                audit_id=audit_id,
                sequence_index=sequence_index,
                event_type=event_type,
                payload=payload, # stored as JSON
                previous_hash=previous_hash,
                entry_hash=entry_hash,
                timestamp=datetime.now(timezone.utc)
            )
            
            session.add(new_entry)
            
            # 5. Update Head Pointer on Record (Optional but good for fast verification)
            record = session.query(AuditRecord).filter(AuditRecord.audit_id == audit_id).first()
            if record:
                record.chain_head_hash = entry_hash
                
            session.commit()
            logger.debug(f"Logged Event {sequence_index} ({event_type}) for Audit {audit_id}")
            return entry_id
            
        except Exception as e:
            session.rollback()
            logger.error(f"AUDIT FAILURE: Could not log event {event_type}: {e}")
            # In GxP, if audit fails, the operation MUST fail. Do not suppress.
            raise e
        finally:
            session.close()

    def capture_config_snapshot(self, job_id: str, config: Dict[str, Any]) -> str:
        """
        TMX-010: Freezes configuration.
        """
        session = self.db_service.get_session()
        try:
            # Canonical Hash
            config_json = json.loads(json.dumps(config, default=str)) # Ensure serializable
            canonical_str = json.dumps(config_json, sort_keys=True)
            config_hash = hashlib.sha256(canonical_str.encode()).hexdigest()
            
            snapshot_id = str(uuid.uuid4())
            snapshot = JobConfigSnapshot(
                snapshot_id=snapshot_id,
                # TMX-3012 will replace with session-context injection.
                organization_id=DEFAULT_ORG_ID,
                job_id=job_id,
                config_json=config_json,
                config_hash=config_hash,
                created_at=datetime.now(timezone.utc)
            )

            session.add(snapshot)
            session.commit()
            logger.info(f"Captured Config Snapshot {snapshot_id} for Job {job_id}")
            return snapshot_id
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to capture config snapshot: {e}")
            raise e
        finally:
            session.close()

    def verify_chain_integrity(self, audit_id: str) -> Dict[str, Any]:
        """
        Recomputes the entire hash chain to verify it hasn't been tampered with.
        """
        session = self.db_service.get_session()
        result = {"valid": True, "broken_at": None, "details": "Integrity Verified"}
        
        try:
            entries = session.query(AuditLogEntry)\
                .filter(AuditLogEntry.audit_id == audit_id)\
                .order_by(AuditLogEntry.sequence_index)\
                .all()
            
            if not entries:
                return {"valid": True, "details": "Empty Chain"}
            
            expected_prev_hash = "GENESIS_HASH"
            
            for entry in entries:
                # 1. Check Link
                if entry.previous_hash != expected_prev_hash:
                    return {
                        "valid": False, 
                        "broken_at": entry.sequence_index,
                        "details": f"Broken Link values. Expected {expected_prev_hash}, Got {entry.previous_hash}"
                    }
                
                # 2. Recompute Hash
                payload_json = json.dumps(entry.payload, sort_keys=True)
                hash_input = f"{entry.previous_hash}{payload_json}"
                recalc_hash = hashlib.sha256(hash_input.encode()).hexdigest()
                
                if recalc_hash != entry.entry_hash:
                     return {
                        "valid": False, 
                        "broken_at": entry.sequence_index,
                        "details": f"Content Tampered. Hash mismatch at index {entry.sequence_index}."
                    }
                
                expected_prev_hash = entry.entry_hash
                
            return result
            
        finally:
            session.close()

    def generate_audit_bundle(self, audit_id: str) -> Dict[str, Any]:
        """
        TMX-022: Export Defense Bundle.
        Returns a complete, verified JSON package of the lifecycle.
        """
        session = self.db_service.get_session()
        try:
            # 1. Fetch Root Record
            record = session.query(AuditRecord).filter(AuditRecord.audit_id == audit_id).first()
            if not record:
                raise ValueError("Audit Trail not found")
            
            # 2. Fetch Config Snapshot
            config_snapshot = {}
            if record.job_id: # record.job is the relationship, record.job_id is the FK
                # We need to query JobConfigSnapshot. 
                # Relation: Job -> Snapshot. Record -> Job.
                # So record.job.config_snapshot
                if record.job and record.job.config_snapshot:
                    config_snapshot = record.job.config_snapshot.config_json
            
            # 3. Fetch Chain
            entries = session.query(AuditLogEntry)\
                .filter(AuditLogEntry.audit_id == audit_id)\
                .order_by(AuditLogEntry.sequence_index)\
                .all()
            
            chain_export = []
            for e in entries:
                chain_export.append({
                    "sequence": e.sequence_index,
                    "timestamp": e.timestamp.isoformat(),
                    "event": e.event_type,
                    "payload": e.payload,
                    "integrity_hash": e.entry_hash,
                    "link_hash": e.previous_hash
                })
                
            # 4. Run Integrity Check
            integrity_report = self.verify_chain_integrity(audit_id)
            
            # 5. Assemble Bundle
            bundle = {
                "bundle_id": str(uuid.uuid4()),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "system_version": "TransMax v3.0-RC1",
                "integrity_status": "PASS" if integrity_report["valid"] else "FAIL",
                "integrity_details": integrity_report.get("details"),
                
                "context": {
                    "audit_id": record.audit_id,
                    "job_id": record.job_id,
                    "final_decision": record.final_decision
                },
                
                "configuration_frozen": config_snapshot,
                "chain_of_custody": chain_export
            }
            
            logger.info(f"Generated Defense Bundle for Audit {audit_id}")
            return bundle
            
        except Exception as e:
            logger.error(f"Bundle Generation Failed: {e}")
            raise e
        finally:
            session.close()
    def log_reviewer_action(self, audit_id: str, action: str, user_id: str, reason: str) -> str:
        """
        TMX-GOV-01: Logs a Human-in-the-Loop decision.
        Action: APPROVE, REJECT, OVERRIDE.
        """
        if action not in ["APPROVE", "REJECT", "OVERRIDE"]:
            raise ValueError(f"Invalid Governance Action: {action}")
            
        payload = {
            "action": action,
            "user_id": user_id,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Log as a distinct event type for queries
        return self.log_event(audit_id, "REVIEW_ACKNOWLEDGED", payload)
