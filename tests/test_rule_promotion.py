"""TMX-3045 — Rule promotion (kill C-13 auto-promote; require signed approval).

These tests prove three invariants:

1. **Pillar 1 / A3 — no rule auto-promotes.** A rule extracted by
   `LearningService` at `confidence >= 0.90` MUST land as `PROPOSED`,
   not `ACTIVE`. THIS is the canonical regression for C-13.

2. **`promote_rule()` is the only path from PROPOSED → ACTIVE.** It
   requires a `RULE_APPROVE` permission and a non-empty reason; it
   stamps `approved_by`, `approved_at`, `approval_reason`; it emits a
   `RULE_PROMOTED` audit event BEFORE the mutation (A1).

3. **No backwards-compat shim.** Auto-promote is gone; no env flag
   re-enables it. A second `promote_rule()` call on an already-`ACTIVE`
   rule raises `ValueError` (we picked raise-over-idempotent because
   it surfaces UI defects).

Test fixture pattern: `fresh_engine_for_db` (from `tests/conftest.py`)
swaps the SQLite engine in-place — same in-place pattern used by
TMX-3012c (see `tests/test_tmx_3012c_request_autoinjection.py`).
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from sqlalchemy.orm import sessionmaker

from app.auth.permissions import Permission, UserRole, has_permission
from app.core.tenant_context import org_context


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def session_factory(fresh_engine_for_db, monkeypatch):
    """Return a sessionmaker bound to the fresh test engine.

    Also propagates the fresh engine/SessionLocal into the three modules
    that import it eagerly at module-load time:

      - `app.models.database` (re-export from `app.core.database`)
      - `app.services.db_service` (used by AuditService.log_event +
        LearningService._save_rule + many others)
      - `app.services.audit_service` is OK because it uses
        `self.db_service.get_session()` which goes through db_service's
        `SessionLocal` reference.

    Without this propagation, `LearningService._save_rule`,
    `promote_rule`, and `AuditService.log_event` would write to whatever
    DB the original (pre-swap) SessionLocal points to — silently
    bypassing the test fixture.

    This is a wider symptom of the import-time-SessionLocal binding.
    A clean fix is to make every service read SessionLocal lazily;
    that's a TMX-3012c follow-up, out of scope here.
    """
    import app.models.database as models_db
    import app.services.db_service as svc_db

    monkeypatch.setattr(models_db, "engine", fresh_engine_for_db.engine)
    monkeypatch.setattr(models_db, "SessionLocal", fresh_engine_for_db.SessionLocal)
    monkeypatch.setattr(svc_db, "engine", fresh_engine_for_db.engine)
    monkeypatch.setattr(svc_db, "SessionLocal", fresh_engine_for_db.SessionLocal)

    yield sessionmaker(bind=fresh_engine_for_db.engine)


@pytest.fixture
def org_id():
    """Use the seeded system default-org for tests (TMX-3010 seeds it)."""
    from app.models.database import DEFAULT_ORG_ID
    return DEFAULT_ORG_ID


def _make_proposed_rule(session, *, confidence=0.95, status="PROPOSED",
                        source_pattern="adverse event",
                        target_correction="événement indésirable"):
    """Insert a PROPOSED rule directly via SQL helper. Returns rule_id."""
    from app.models.models import TranslationRule
    rule_id = str(uuid.uuid4())
    rule = TranslationRule(
        rule_id=rule_id,
        source_pattern=source_pattern,
        target_correction=target_correction,
        confidence_score=confidence,
        status=status,
        context_tag="test",
    )
    session.add(rule)
    session.commit()
    return rule_id


# ---------------------------------------------------------------------------
# AC-1 — canonical C-13 regression: confidence >= 0.90 lands PROPOSED
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("confidence", [0.90, 0.901, 0.95, 1.0, 0.0, 0.5, 0.89, 0.899])
@pytest.mark.asyncio
async def test_learning_service_never_auto_promotes(confidence):
    """C-13 fix: NO confidence value triggers auto-promotion to ACTIVE.

    This is the canonical regression test. We capture the `status` argument
    that `LearningService._save_rule` is called with and assert it is
    `"PROPOSED"` for ALL confidence values (including the previous
    auto-promote threshold of 0.90).

    Before the fix: confidence>=0.90 would call `_save_rule(..., status="ACTIVE")`.
    After the fix: every call goes through `_save_rule(..., status="PROPOSED")`.

    We patch `_save_rule` (rather than going to DB) for two reasons:
      1. The unit under test is the threshold logic, not persistence.
      2. `db_service.get_session()` reads the module-level SessionLocal
         imported from `app.models.database`, which doesn't pick up the
         conftest in-place swap (it would need a deeper fixture refactor
         outside this ticket's scope — TMX-3012c-followup).
    """
    from app.services.learning_service import LearningService

    fake_response = MagicMock()
    fake_response.content = (
        '{"rule_extracted": true, "source_pattern": "AE", '
        f'"target_correction": "X", "confidence": {confidence}, '
        '"explanation": "test"}'
    )

    captured_status = {}

    def fake_save_rule(self, *, source_pattern, target_correction,
                       confidence, status, origin_id):
        captured_status["status"] = status
        captured_status["confidence"] = confidence
        captured_status["source_pattern"] = source_pattern

    with patch("app.services.learning_service.get_llm") as mock_get_llm, \
         patch("app.services.learning_service.ResilienceService.resilient_llm_call",
               new=AsyncMock(return_value=fake_response)), \
         patch.object(LearningService, "_save_rule", fake_save_rule):
        mock_get_llm.return_value = MagicMock()
        svc = LearningService()
        await svc.process_learning_event(
            segment_id="seg-canonical-c13",
            human_correction="X",
            source_text="adverse event",
            mt_text="événement adverse",
        )

    assert captured_status, (
        "_save_rule was never called — the LLM mock or rule_extracted gate "
        "broke before reaching persistence; not the C-13 fix path."
    )
    assert captured_status["status"] == "PROPOSED", (
        f"C-13 REGRESSION: confidence={confidence} landed with "
        f"status={captured_status['status']!r}, expected 'PROPOSED'. "
        f"Auto-promote has been re-introduced — the silent-fallback "
        f"hazard A3 forbids."
    )
    assert math.isclose(
        float(captured_status["confidence"]), confidence, abs_tol=1e-6
    )


# ---------------------------------------------------------------------------
# AC-2 — promote_rule with permission flips PROPOSED → ACTIVE + stamps
# ---------------------------------------------------------------------------


def test_promote_rule_with_permission_flips_to_active(session_factory, org_id):
    from app.services.rule_promotion import promote_rule
    from app.models.models import TranslationRule

    s = session_factory()
    try:
        with org_context(org_id):
            rule_id = _make_proposed_rule(s, confidence=0.95)

            t0 = datetime.now(timezone.utc)
            promoted = promote_rule(
                rule_id=rule_id,
                approver_id="user-curator-001",
                approver_role=UserRole.CURATOR,
                reason="Verified canonical pharma terminology against MedDRA glossary v26.1",
                db=s,
            )
            t1 = datetime.now(timezone.utc)

            assert promoted.status == "ACTIVE"
            assert promoted.approved_by == "user-curator-001"
            assert promoted.approval_reason.startswith("Verified canonical")
            assert promoted.approved_at is not None
            # SQLite strips tzinfo on read-back; promoted.approved_at is
            # naive when reloaded but we know promote_rule wrote a tz-aware
            # datetime. Compare against the naive UTC instant for portability.
            t0_naive = t0.replace(tzinfo=None)
            t1_naive = t1.replace(tzinfo=None)
            approved_naive = promoted.approved_at
            if approved_naive.tzinfo is not None:
                approved_naive = approved_naive.replace(tzinfo=None)
            assert t0_naive <= approved_naive <= t1_naive, (
                "approved_at must be the UTC instant the promotion succeeded."
            )

            # Re-read from DB to ensure it persisted, not just held in memory.
            persisted = s.query(TranslationRule).filter_by(rule_id=rule_id).one()
            assert persisted.status == "ACTIVE"
            assert persisted.approved_by == "user-curator-001"
    finally:
        s.close()


# ---------------------------------------------------------------------------
# AC-3 — promote_rule without permission raises PermissionError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role_without_perm", [
    UserRole.REVIEWER,    # reviewers approve translations, NOT rules
    UserRole.TRANSLATOR,
    UserRole.VIEWER,
])
def test_promote_rule_without_permission_raises(role_without_perm, session_factory, org_id):
    from app.services.rule_promotion import promote_rule
    from app.models.models import TranslationRule

    s = session_factory()
    try:
        with org_context(org_id):
            rule_id = _make_proposed_rule(s)

            with pytest.raises(PermissionError) as exc:
                promote_rule(
                    rule_id=rule_id,
                    approver_id="user-no-perm",
                    approver_role=role_without_perm,
                    reason="should not be allowed",
                    db=s,
                )
            assert "RULE_APPROVE" in str(exc.value)

            # Verify the rule was NOT mutated.
            unchanged = s.query(TranslationRule).filter_by(rule_id=rule_id).one()
            assert unchanged.status == "PROPOSED"
            assert unchanged.approved_by is None
            assert unchanged.approved_at is None
    finally:
        s.close()


# ---------------------------------------------------------------------------
# AC-4 — empty reason / missing rule / already-active raise ValueError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("empty_reason", ["", "   ", "\t\n"])
def test_promote_rule_empty_reason_raises(empty_reason, session_factory, org_id):
    from app.services.rule_promotion import promote_rule

    s = session_factory()
    try:
        with org_context(org_id):
            rule_id = _make_proposed_rule(s)
            with pytest.raises(ValueError) as exc:
                promote_rule(
                    rule_id=rule_id,
                    approver_id="user-curator-001",
                    approver_role=UserRole.CURATOR,
                    reason=empty_reason,
                    db=s,
                )
            assert "reason" in str(exc.value).lower()
    finally:
        s.close()


def test_promote_rule_missing_rule_raises(session_factory, org_id):
    from app.services.rule_promotion import promote_rule

    s = session_factory()
    try:
        with org_context(org_id):
            with pytest.raises(ValueError) as exc:
                promote_rule(
                    rule_id="does-not-exist",
                    approver_id="user-curator-001",
                    approver_role=UserRole.CURATOR,
                    reason="trying to promote a ghost",
                    db=s,
                )
            assert "not found" in str(exc.value).lower() or "does-not-exist" in str(exc.value)
    finally:
        s.close()


def test_promote_rule_already_active_raises(session_factory, org_id):
    """Idempotent-or-raise: we picked RAISE because re-promoting an
    already-active rule is a UI defect worth surfacing."""
    from app.services.rule_promotion import promote_rule

    s = session_factory()
    try:
        with org_context(org_id):
            rule_id = _make_proposed_rule(s, status="ACTIVE")
            with pytest.raises(ValueError) as exc:
                promote_rule(
                    rule_id=rule_id,
                    approver_id="user-curator-001",
                    approver_role=UserRole.CURATOR,
                    reason="double-promote attempt",
                    db=s,
                )
            assert "already" in str(exc.value).lower() or "active" in str(exc.value).lower()
    finally:
        s.close()


# ---------------------------------------------------------------------------
# AC-5 — promote_rule emits a RULE_PROMOTED audit event BEFORE mutation (A1)
# ---------------------------------------------------------------------------


def test_promote_rule_emits_audit_event(session_factory, org_id):
    """A1: the audit event MUST be emitted before the row is mutated.

    We assert on the event's existence + payload + ordering relative
    to the rule status change. Ordering check: if the audit-emit fails,
    the rule must NOT be promoted.
    """
    from app.services.rule_promotion import promote_rule
    from app.models.models import TranslationRule, AuditLogEntry

    s = session_factory()
    try:
        with org_context(org_id):
            rule_id = _make_proposed_rule(s, confidence=0.92)

            promote_rule(
                rule_id=rule_id,
                approver_id="user-curator-002",
                approver_role=UserRole.CURATOR,
                reason="signed off after MedDRA cross-check",
                db=s,
            )

            # Find the RULE_PROMOTED event. v1 audit chain stores in AuditLogEntry.
            entries = s.query(AuditLogEntry).filter(
                AuditLogEntry.event_type == "RULE_PROMOTED"
            ).all()
            assert len(entries) >= 1, (
                "A1 violation: promote_rule did not emit a RULE_PROMOTED "
                "audit event. Every state change in a regulated path MUST "
                "audit before any side effect."
            )
            payload = entries[-1].payload
            assert payload["rule_id"] == rule_id
            assert payload["approver_id"] == "user-curator-002"
            assert payload["source_pattern"] == "adverse event"
            assert math.isclose(
                float(payload["confidence_at_promotion"]), 0.92, abs_tol=1e-6
            )
            assert "MedDRA" in payload["reason"]
    finally:
        s.close()


def test_promote_rule_audit_failure_aborts_promotion(session_factory, org_id):
    """If audit-write fails, the rule MUST NOT be promoted (A1 ordering)."""
    from app.services import rule_promotion as rp_module
    from app.models.models import TranslationRule

    s = session_factory()
    try:
        with org_context(org_id):
            rule_id = _make_proposed_rule(s)

            # Force log_event to fail.
            with patch.object(
                rp_module.AuditService,
                "log_event",
                side_effect=RuntimeError("simulated audit-store outage"),
            ):
                with pytest.raises(RuntimeError):
                    rp_module.promote_rule(
                        rule_id=rule_id,
                        approver_id="user-curator-003",
                        approver_role=UserRole.CURATOR,
                        reason="will fail at audit time",
                        db=s,
                    )

            # Rule must remain PROPOSED — no silent promotion.
            unchanged = s.query(TranslationRule).filter_by(rule_id=rule_id).one()
            assert unchanged.status == "PROPOSED"
            assert unchanged.approved_by is None
    finally:
        s.close()


# ---------------------------------------------------------------------------
# AC-6 — RULE_APPROVE permission wired correctly into role map
# ---------------------------------------------------------------------------


def test_role_permission_map_includes_rule_approve():
    """Verify the role→permission map at the source. Pillar 1 wiring."""
    assert hasattr(Permission, "RULE_APPROVE"), (
        "Permission.RULE_APPROVE must exist for TMX-3045."
    )
    assert has_permission(UserRole.ADMIN, Permission.RULE_APPROVE)
    assert has_permission(UserRole.PROJECT_MANAGER, Permission.RULE_APPROVE)
    assert has_permission(UserRole.CURATOR, Permission.RULE_APPROVE)
    assert not has_permission(UserRole.REVIEWER, Permission.RULE_APPROVE)
    assert not has_permission(UserRole.TRANSLATOR, Permission.RULE_APPROVE)
    assert not has_permission(UserRole.VIEWER, Permission.RULE_APPROVE)


# ---------------------------------------------------------------------------
# AC-8 — feedback endpoint does NOT auto-promote (regression guard)
# ---------------------------------------------------------------------------


def test_feedback_endpoint_does_not_auto_promote():
    """The /feedback router MUST stamp PENDING_APPROVAL or PROPOSED, never
    ACTIVE. (Already true in current code — this guards against regression.)

    This test does NOT use `fresh_engine_for_db`: the FastAPI app uses
    `get_db_service()` (a process-wide singleton bound to whichever
    SessionLocal was imported at module load), which fights any in-place
    swap when run as part of the suite. We use a unique source_pattern
    per run to avoid colliding with prior test runs, then read directly
    from the same DatabaseService singleton.
    """
    import os
    import uuid as _uuid
    os.environ["AUTH_MODE"] = "none"
    from fastapi.testclient import TestClient
    from app.main import app
    from app.models.models import TranslationRule
    from app.services.db_service import get_db_service
    from app.models.database import DEFAULT_ORG_ID

    unique_marker = f"feedback_loop_marker_{_uuid.uuid4().hex[:8]}"

    client = TestClient(app)
    payload = {
        "source_text": unique_marker,
        "target_text": "translated_marker",
        "corrected_text": "fixed_marker",
        "rating": "negative",
        "target_language": "fr",
    }
    resp = client.post("/api/knowledge/feedback", json=payload)
    assert resp.status_code == 200, resp.text

    # Read back the rule from the SAME DB the app wrote to.
    s = get_db_service().get_session()
    try:
        with org_context(DEFAULT_ORG_ID):
            rule = s.query(TranslationRule).filter(
                TranslationRule.source_pattern == unique_marker
            ).one()
            assert rule.status != "ACTIVE", (
                "A3 violation: feedback endpoint silently activated a rule "
                "without human approval. Should be PENDING_APPROVAL or PROPOSED."
            )
            assert rule.status in ("PENDING_APPROVAL", "PROPOSED")
    finally:
        s.close()
