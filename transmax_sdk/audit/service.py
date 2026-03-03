"""Hash-chained audit trail implementation (headless, no DB dependency)."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.telemetry.protocol import TelemetryProtocol

GENESIS_HASH = "GENESIS_HASH"


@dataclass
class AuditEntry:
    """A single entry in the audit chain."""
    entry_id: str
    audit_id: str
    sequence_index: int
    event_type: str
    payload: Dict[str, Any]
    previous_hash: str
    entry_hash: str
    timestamp: str


@dataclass
class AuditTrail:
    """In-memory audit trail with hash chain."""
    audit_id: str
    job_id: str
    created_at: str
    entries: List[AuditEntry] = field(default_factory=list)
    chain_head_hash: str = GENESIS_HASH
    config_snapshot: Optional[Dict[str, Any]] = None
    config_hash: Optional[str] = None
    final_decision: Optional[str] = None


class HashChainedAuditTrail:
    """GxP-compliant tamper-evident audit trail.

    Implements hash-chaining (blockchain-style) for tamper evidence.
    Can work headless (in-memory) or delegate to a DB-backed service.
    """

    def __init__(self, telemetry: Optional[TelemetryProtocol] = None) -> None:
        self._telemetry = telemetry or NoOpTelemetry()
        self._trails: Dict[str, AuditTrail] = {}

    def create_trail(self, job_id: str) -> str:
        """Create a new audit trail. Returns audit_id."""
        audit_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self._trails[audit_id] = AuditTrail(
            audit_id=audit_id, job_id=job_id, created_at=now,
        )
        self._telemetry.counter("transmax_audit_events_total", labels={"event_type": "TRAIL_CREATED"})
        return audit_id

    def log_event(self, audit_id: str, event_type: str, payload: Dict[str, Any]) -> str:
        """Append a tamper-evident event to the chain."""
        trail = self._trails.get(audit_id)
        if trail is None:
            raise ValueError(f"Audit trail not found: {audit_id}")

        with self._telemetry.span("audit.log_event", {"event_type": event_type}):
            sequence_index = len(trail.entries)
            previous_hash = trail.chain_head_hash

            # Canonical payload
            payload_json = json.dumps(payload, sort_keys=True, default=str)

            # Hash: SHA256(previous_hash + payload)
            hash_input = f"{previous_hash}{payload_json}"
            entry_hash = hashlib.sha256(hash_input.encode()).hexdigest()

            entry_id = str(uuid.uuid4())
            entry = AuditEntry(
                entry_id=entry_id,
                audit_id=audit_id,
                sequence_index=sequence_index,
                event_type=event_type,
                payload=payload,
                previous_hash=previous_hash,
                entry_hash=entry_hash,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

            trail.entries.append(entry)
            trail.chain_head_hash = entry_hash

            self._telemetry.counter("transmax_audit_events_total", labels={"event_type": event_type})
            return entry_id

    def capture_config(self, audit_id: str, config: Dict[str, Any]) -> str:
        """Freeze configuration snapshot for reproducibility."""
        trail = self._trails.get(audit_id)
        if trail is None:
            raise ValueError(f"Audit trail not found: {audit_id}")

        canonical = json.dumps(config, sort_keys=True, default=str)
        config_hash = hashlib.sha256(canonical.encode()).hexdigest()
        trail.config_snapshot = config
        trail.config_hash = config_hash
        return config_hash

    def verify_integrity(self, audit_id: str) -> Dict[str, Any]:
        """Verify the entire hash chain for tampering."""
        trail = self._trails.get(audit_id)
        if trail is None:
            raise ValueError(f"Audit trail not found: {audit_id}")

        if not trail.entries:
            return {"valid": True, "broken_at": None, "details": "Empty chain"}

        expected_prev = GENESIS_HASH

        for entry in trail.entries:
            if entry.previous_hash != expected_prev:
                return {
                    "valid": False,
                    "broken_at": entry.sequence_index,
                    "details": f"Broken link at index {entry.sequence_index}",
                }

            payload_json = json.dumps(entry.payload, sort_keys=True, default=str)
            recalc = hashlib.sha256(f"{entry.previous_hash}{payload_json}".encode()).hexdigest()

            if recalc != entry.entry_hash:
                return {
                    "valid": False,
                    "broken_at": entry.sequence_index,
                    "details": f"Content tampered at index {entry.sequence_index}",
                }

            expected_prev = entry.entry_hash

        return {"valid": True, "broken_at": None, "details": "Integrity verified"}

    def export_bundle(self, audit_id: str) -> Dict[str, Any]:
        """Export complete defense bundle."""
        trail = self._trails.get(audit_id)
        if trail is None:
            raise ValueError(f"Audit trail not found: {audit_id}")

        integrity = self.verify_integrity(audit_id)

        chain_export = [
            {
                "sequence": e.sequence_index,
                "timestamp": e.timestamp,
                "event": e.event_type,
                "payload": e.payload,
                "integrity_hash": e.entry_hash,
                "link_hash": e.previous_hash,
            }
            for e in trail.entries
        ]

        return {
            "bundle_id": str(uuid.uuid4()),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "system_version": "TransMax SDK v0.1.0",
            "integrity_status": "PASS" if integrity["valid"] else "FAIL",
            "integrity_details": integrity["details"],
            "context": {
                "audit_id": trail.audit_id,
                "job_id": trail.job_id,
                "final_decision": trail.final_decision,
            },
            "configuration_frozen": trail.config_snapshot,
            "chain_of_custody": chain_export,
        }

    def log_reviewer_action(
        self, audit_id: str, action: str, user_id: str, reason: str
    ) -> str:
        """TMX-GOV-01: Log a human-in-the-loop decision."""
        if action not in ("APPROVE", "REJECT", "OVERRIDE"):
            raise ValueError(f"Invalid action: {action}")

        return self.log_event(audit_id, "REVIEW_ACKNOWLEDGED", {
            "action": action,
            "user_id": user_id,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_trail(self, audit_id: str) -> Optional[AuditTrail]:
        """Get a trail by ID (for testing/inspection)."""
        return self._trails.get(audit_id)
