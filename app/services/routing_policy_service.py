"""Per-tenant LLM routing-policy service (TMX-ROUTER-3).

Read/write the `routing_policies` row that overlays the default model-routing
policy for an organization. Writes are RBAC-gated (`ROUTING_CONFIGURE`),
validated (a bad override can't silently route to nowhere — A3), and recorded
with `updated_by`/`updated_at` + a structured audit log line.

Audit note: the v1/v2 audit chains are job-scoped; a tenant config change is
not tied to a job, so it cannot use those chains today. We stamp who/when on
the row and emit a structured log. Spawned TMX-ROUTER-3a to chain config
changes once a system-level (job-less) audit trail exists.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.auth.permissions import Permission, UserRole, has_permission
from app.core.model_registry import Complexity, ModelTier, Task
from app.models.database import RoutingPolicy

logger = logging.getLogger(__name__)

_VALID_TASKS = {t.value for t in Task}
_VALID_COMPLEXITIES = {c.value for c in Complexity}
_VALID_TIERS = {t.value for t in ModelTier}


def validate_overrides(overrides: dict) -> None:
    """Reject malformed overrides (A3 — fail loud, never route to nowhere).

    Keys must be ``"task:complexity"`` with known task + complexity; values
    must be a known tier name.
    """
    if not isinstance(overrides, dict):
        raise ValueError("overrides must be a dict of 'task:complexity' -> tier")
    for key, tier in overrides.items():
        parts = str(key).split(":")
        if len(parts) != 2 or parts[0] not in _VALID_TASKS or parts[1] not in _VALID_COMPLEXITIES:
            raise ValueError(
                f"Invalid override key {key!r}; expected 'task:complexity' with "
                f"task in {sorted(_VALID_TASKS)} and complexity in {sorted(_VALID_COMPLEXITIES)}."
            )
        if tier not in _VALID_TIERS:
            raise ValueError(
                f"Invalid tier {tier!r} for {key!r}; expected one of {sorted(_VALID_TIERS)}."
            )


def get_policy_overrides(org_id: str, db: Session) -> dict:
    """Return the org's ENABLED routing overrides, or ``{}`` if none/disabled."""
    row = (
        db.query(RoutingPolicy)
        .filter(RoutingPolicy.organization_id == org_id)
        .one_or_none()
    )
    if row is None or not row.enabled:
        return {}
    return dict(row.overrides or {})


def get_policy(org_id: str, db: Session) -> RoutingPolicy | None:
    """Return the org's RoutingPolicy row (or None)."""
    return (
        db.query(RoutingPolicy)
        .filter(RoutingPolicy.organization_id == org_id)
        .one_or_none()
    )


def upsert_policy(
    org_id: str,
    overrides: dict,
    enabled: bool,
    actor_id: str,
    actor_role: UserRole,
    *,
    db: Session,
) -> RoutingPolicy:
    """Create/update the org's routing policy. RBAC + validation + audit-log.

    Raises:
        PermissionError: actor lacks `ROUTING_CONFIGURE`.
        ValueError: overrides malformed.
    """
    if not has_permission(actor_role, Permission.ROUTING_CONFIGURE):
        raise PermissionError(
            f"Role {getattr(actor_role, 'value', actor_role)!r} lacks "
            f"Permission.ROUTING_CONFIGURE; only ADMIN/PROJECT_MANAGER may edit routing."
        )
    validate_overrides(overrides)

    # Audit-log BEFORE the mutation (A1 spirit; chained-audit gap → TMX-ROUTER-3a).
    logger.info(
        "ROUTING_POLICY_UPDATED org=%s by=%s enabled=%s overrides=%s",
        org_id, actor_id, enabled, overrides,
    )

    row = get_policy(org_id, db)
    if row is None:
        row = RoutingPolicy(
            organization_id=org_id, overrides=overrides,
            enabled=enabled, updated_by=actor_id,
        )
        db.add(row)
    else:
        row.overrides = overrides
        row.enabled = enabled
        row.updated_by = actor_id
    db.commit()
    db.refresh(row)
    return row
