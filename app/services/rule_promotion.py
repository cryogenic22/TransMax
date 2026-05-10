"""TMX-3045 / Pillar 1 — signed promotion of a learned translation rule.

Capabilities Spec Pillar 1 ("no rule joins the active rule-base without an
explicit human signature") and TransMax addendum A3 ("no silent fallbacks
in regulated paths") together require: any path from `PROPOSED` to
`ACTIVE` must record an authenticated approver, a justification, and an
audit event in the chained-hash log BEFORE the row mutates.

This module is the **only** sanctioned path for that state transition.
The old auto-promote branch in `app.services.learning_service` (the C-13
hazard from the 2026-05-09 audit) has been removed.

Module is intentionally small and dependency-light: the only public API
is `promote_rule()`, kw-only `db: Session` injected by the caller so the
audit event and the row mutation share one transaction.

Audit chain note: `AuditService.log_event` is the v1 chain. TMX-3101 will
swap the v1 chain for `audit_events_v2`; rule promotion is one of the
callers TMX-3101 will rewrite. Until then the v1 chain is the contract,
matching every other regulated state transition in the codebase.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.auth.permissions import Permission, UserRole, has_permission
from app.models.models import TranslationRule
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


def promote_rule(
    rule_id: str,
    approver_id: str,
    approver_role: UserRole,
    reason: str,
    *,
    db: Session,
    audit_service: Optional[AuditService] = None,
) -> TranslationRule:
    """Promote a `PROPOSED` rule to `ACTIVE` with a signed human approval.

    Pillar 1 / A3 / A1 — every active rule MUST carry a verifiable human
    signature, AND the promotion must be audit-logged BEFORE the row is
    mutated (so a tampered or aborted promotion cannot be silently
    backed-out without leaving a trace).

    Args:
        rule_id: target rule's primary key.
        approver_id: stable user id of the human signing this approval.
        approver_role: resolved `UserRole` of the approver. Caller (the
            FastAPI endpoint or the test harness) is responsible for
            extracting this from the auth token; we do not re-look-up
            the user from the DB.
        reason: free-text justification. Must be non-empty after strip.
        db: kw-only — SQLAlchemy session that owns the rule row. The
            audit event and the row mutation share this session for
            transactional integrity.
        audit_service: kw-only — optional injected `AuditService`; defaults
            to a fresh instance. Tests inject a mock to assert on
            `log_event` ordering.

    Returns:
        The updated `TranslationRule` (status=`ACTIVE`, approval fields
        populated). Read from the same session, refreshed.

    Raises:
        PermissionError: approver lacks `Permission.RULE_APPROVE`.
        ValueError: `reason` empty/whitespace, or `rule_id` not found,
            or rule is already `ACTIVE` (idempotent-or-raise: we picked
            **raise** because attempting to re-promote an already-active
            rule is a UI defect worth surfacing — a curator would not click
            promote twice).
        RuntimeError: audit-event write failed; rule is NOT promoted.

    Note: there is no `TenantContextMissing` codepath here — the caller
    must supply a session already scoped to the right tenant. The
    `TenantScopedMixin` auto-filter will refuse to load `rule` from the
    wrong tenant; that surfaces as `ValueError("rule not found")` here,
    which is the right A3 outcome.
    """
    # ---- Validate inputs (cheap checks first; A3 fail-loud) ----
    if not has_permission(approver_role, Permission.RULE_APPROVE):
        raise PermissionError(
            f"Role {approver_role.value!r} lacks Permission.RULE_APPROVE; "
            f"only ADMIN, PROJECT_MANAGER, and CURATOR may sign rule promotions."
        )

    if reason is None or not reason.strip():
        raise ValueError(
            "Empty reason. Pillar 1 requires a non-empty written "
            "justification on every rule promotion."
        )

    rule = db.query(TranslationRule).filter(TranslationRule.rule_id == rule_id).one_or_none()
    if rule is None:
        raise ValueError(f"Rule not found: {rule_id!r}")

    if rule.status == "ACTIVE":
        raise ValueError(
            f"Rule {rule_id!r} is already ACTIVE; refusing to double-stamp. "
            f"If you need to amend approval metadata, file a TMX-3045-style "
            f"override ticket — direct re-promotion is not supported."
        )

    # ---- A1: emit audit event BEFORE the row mutates. ----
    # If the audit-event write fails, the rule MUST NOT be promoted. We
    # don't catch the AuditService exception; we let it propagate so the
    # caller's transaction fails too (db.rollback() on outer error path).
    audit = audit_service or AuditService()
    audit_id = audit.create_audit_trail(job_id=None)
    audit.log_event(
        audit_id=audit_id,
        event_type="RULE_PROMOTED",
        payload={
            "rule_id": rule_id,
            "approver_id": approver_id,
            "approver_role": approver_role.value,
            "source_pattern": rule.source_pattern,
            "target_correction": rule.target_correction,
            "confidence_at_promotion": rule.confidence_score,
            "reason": reason.strip(),
            "promoted_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    )

    # ---- Mutate row. ----
    now_utc = datetime.now(timezone.utc)
    rule.status = "ACTIVE"
    rule.approved_by = approver_id
    rule.approved_at = now_utc
    rule.approval_reason = reason.strip()
    db.add(rule)
    db.commit()
    db.refresh(rule)

    logger.info(
        "Rule %s promoted to ACTIVE by %s (role=%s); audit_id=%s",
        rule_id, approver_id, approver_role.value, audit_id,
    )
    return rule
