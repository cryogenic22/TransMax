"""Audit trail protocol: contract for audit implementations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class AuditTrailProtocol(Protocol):
    """Interface for audit trail implementations."""

    def create_trail(self, job_id: str) -> str:
        """Create a new audit trail for a job. Returns audit_id."""
        ...

    def log_event(self, audit_id: str, event_type: str, payload: Dict[str, Any]) -> str:
        """Log an event to the audit trail. Returns entry_id."""
        ...

    def verify_integrity(self, audit_id: str) -> Dict[str, Any]:
        """Verify the hash chain integrity. Returns {valid, broken_at, details}."""
        ...

    def export_bundle(self, audit_id: str) -> Dict[str, Any]:
        """Export a complete defense bundle."""
        ...
