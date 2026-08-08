"""
TMX-SEAM-WIRE — wire the ADR-0009 clause 3 result block into the live
`GET /api/v1/translations/{job_id}/result` path, HONESTLY (A3).

Every field the route now populates must trace to a real artefact:

  * `disposition`  <- the persisted `QualityScorecard.status` (the legacy
    count-based `quality_gate.py::evaluate_verdict` verdict) — never
    `Document.status` (workflow state, a different concept).
  * `provenance`   <- the job's own `CONFIG_SNAPSHOT_CAPTURED` v2 audit
    event payload (the exact blob `_config_snapshot.build_config_snapshot`
    froze at job start) + the segments' real `translation_source`. Any
    field with no backing artefact (model_version, language_tier) stays
    None — never a default, never a plausible-looking constant.
  * `audit`        <- the job's real v2 chain head hash, cross-checked
    against the independent `/verify_v2` endpoint. None if there is no
    v2 chain — never a placeholder.
  * `mqm`          <- MUST stay None. The MQM engine is shadow-only; the
    live verdict is still the legacy scorer. Synthesizing an MqmSummary
    here would be the exact unearned-claim defect this program keeps
    fixing.

These tests fail against pre-TMX-SEAM-WIRE `translations.py` (the fields
don't exist on the route's response at all, or match a wrong source), and
pass once `get_job_result` is wired per the docstrings above.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_app_client(fresh_engine_for_db):
    """A TestClient against `app.main:app` with `app.core.database` swapped
    to a fresh tmp SQLite DB. Returns (client, core_db, session)."""
    from app.main import app

    core_db = fresh_engine_for_db
    Session = sessionmaker(bind=core_db.engine)
    session = Session()
    client = TestClient(app)
    try:
        yield client, core_db, session
    finally:
        session.close()


def _seed_org(engine, org_id: str) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO organizations "
                "(id, name, slug, org_kind, is_active, created_at, updated_at) "
                "VALUES (:id, :name, :slug, 'customer', 1, :ts, :ts)"
            ).bindparams(
                id=org_id, name=f"org-{org_id[:8]}",
                slug=f"org-{org_id[:8]}", ts=now_iso,
            )
        )


def _seed_completed_job(
    core_db,
    org_id: str,
    *,
    scorecard_status: str | None,
    translation_source: str = "LLM",
) -> str:
    """Insert a TRANSLATED Document + two Segments (+ optional
    QualityScorecard) directly, bypassing the pipeline (the route only
    needs the persisted rows, not a live run)."""
    from app.core.tenant_context import org_context
    from app.models.database import Document, DocumentStatus, Segment
    from app.models.models import QualityScorecard

    job_id = str(uuid.uuid4())
    Session = sessionmaker(bind=core_db.engine)
    session = Session()
    try:
        with org_context(org_id):
            doc = Document(
                id=job_id,
                name="doc.txt",
                source_language="en",
                target_language="fr",
                status=DocumentStatus.TRANSLATED.value,
                updated_at=datetime.now(timezone.utc),
            )
            session.add(doc)
            session.add(Segment(
                document_id=job_id, order_index=0,
                source_text="Take 10mg daily.",
                translated_text="Prenez 10mg par jour.",
                status="translated",
                translation_source=translation_source,
            ))
            session.add(Segment(
                document_id=job_id, order_index=1,
                source_text="Do not exceed the dose.",
                translated_text="Ne dépassez pas la dose.",
                status="translated",
                translation_source=translation_source,
            ))
            if scorecard_status is not None:
                session.add(QualityScorecard(
                    job_id=job_id,
                    status=scorecard_status,
                    critical_defect_count=0,
                    major_defect_count=1 if scorecard_status == "REVIEW_REQUIRED" else 0,
                    minor_defect_count=0,
                ))
            session.commit()
    finally:
        session.close()
    return job_id


def _write_config_snapshot_event(core_db, org_id: str, job_id: str, config_snapshot: dict) -> None:
    from app.core.tenant_context import org_context
    from app.services.audit_writer_v2 import AuditWriterV2

    writer = AuditWriterV2(session_factory=core_db.SessionLocal)
    with org_context(org_id):
        writer.record_event(
            job_id=job_id,
            event_type="AUDIT_TRAIL_INITIALIZED",
            actor_id=None,
            actor_kind="system",
            payload={"timestamp": datetime.now(timezone.utc).isoformat()},
        )
        writer.record_event(
            job_id=job_id,
            event_type="CONFIG_SNAPSHOT_CAPTURED",
            actor_id=None,
            actor_kind="system",
            payload=config_snapshot,
        )


_SAMPLE_CONFIG_SNAPSHOT = {
    "request": {"doc_id": "irrelevant", "target_language": "fr"},
    "system": {
        "model": "gpt-4o-2024-08-06",
        "prompts": {
            "translator": {"version": "1.2.0", "content_hash": "deadbeef" * 8},
            "fixer": {"version": "1.0.0", "content_hash": "cafebabe" * 8},
            "reviewer": {"version": "1.0.0", "content_hash": "f00dface" * 8},
        },
    },
}


# ---------------------------------------------------------------------------
# (a) disposition matches the real verdict + audit.chain_head_hash matches
#     the independent verifier.
# ---------------------------------------------------------------------------


def test_result_carries_contract_version_and_real_disposition(fresh_app_client):
    client, core_db, _ = fresh_app_client
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    with org_context(DEFAULT_ORG_ID):
        job_id = _seed_completed_job(
            core_db, DEFAULT_ORG_ID, scorecard_status="REVIEW_REQUIRED",
        )
        _write_config_snapshot_event(
            core_db, DEFAULT_ORG_ID, job_id, _SAMPLE_CONFIG_SNAPSHOT,
        )

    resp = client.get(f"/api/v1/translations/{job_id}/result")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["contract_version"] == "1.1.0"
    # The verdict came from QualityScorecard.status (REVIEW_REQUIRED), NOT
    # from Document.status (which is "translated").
    assert data["disposition"] == "REVIEW_REQUIRED"

    assert data["audit"] is not None
    reported_head = data["audit"]["chain_head_hash"]
    assert reported_head is not None

    verify_resp = client.get(f"/api/v1/audit/{job_id}/verify_v2")
    assert verify_resp.status_code == 200, verify_resp.text
    independent_head = verify_resp.json()["chain_head_hash"]
    assert reported_head == independent_head, (
        "result.audit.chain_head_hash must match the independent verifier's "
        "own chain_head_hash for the SAME job — a claim that disagrees with "
        "its own verifier is worse than no claim at all (A1)."
    )


def test_quality_summary_decision_is_the_scorecard_verdict_not_doc_status(fresh_app_client):
    """TMX-VALSUMMARY-VERDICT (A3): the legacy `quality_summary.decision` must
    report the REAL scorecard verdict, never `Document.status`. Here the doc is
    TRANSLATED but the scorecard says REVIEW_REQUIRED — a reviewer must see the
    verdict, not the workflow state that looks clean."""
    client, core_db, _ = fresh_app_client
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    with org_context(DEFAULT_ORG_ID):
        job_id = _seed_completed_job(
            core_db, DEFAULT_ORG_ID, scorecard_status="REVIEW_REQUIRED",
        )

    resp = client.get(f"/api/v1/translations/{job_id}/result")
    assert resp.status_code == 200, resp.text
    summary = resp.json()["quality_summary"]

    assert summary["decision"] == "REVIEW_REQUIRED"
    assert summary["decision"].lower() != "translated", (
        "decision must be the scorecard verdict, never the Document workflow state"
    )
    # counts come from the real scorecard (REVIEW_REQUIRED seeds one major).
    assert summary["major_count"] == 1


def test_quality_summary_says_not_scored_when_no_scorecard(fresh_app_client):
    """No scorecard must read as an explicit NOT_SCORED — never Document.status
    and never a fabricated clean verdict. The zero counts must carry a
    non-verdict decision so they cannot read as a clean pass (A3)."""
    client, core_db, _ = fresh_app_client
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    with org_context(DEFAULT_ORG_ID):
        job_id = _seed_completed_job(core_db, DEFAULT_ORG_ID, scorecard_status=None)

    resp = client.get(f"/api/v1/translations/{job_id}/result")
    assert resp.status_code == 200, resp.text
    summary = resp.json()["quality_summary"]

    assert summary["decision"] == "NOT_SCORED"
    assert summary["decision"].lower() != "translated"


def test_disposition_blocked_when_scorecard_says_blocked(fresh_app_client):
    """A different real verdict (BLOCKED) is not silently normalised to PASS."""
    client, core_db, _ = fresh_app_client
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    with org_context(DEFAULT_ORG_ID):
        job_id = _seed_completed_job(
            core_db, DEFAULT_ORG_ID, scorecard_status="BLOCKED",
        )

    resp = client.get(f"/api/v1/translations/{job_id}/result")
    assert resp.status_code == 200, resp.text
    assert resp.json()["disposition"] == "BLOCKED"


def test_no_scorecard_yields_none_disposition_not_a_guess(fresh_app_client):
    """No QualityScorecard row -> disposition None. Never inferred from
    Document.status (which would read 'translated' -> a fabricated PASS)."""
    client, core_db, _ = fresh_app_client
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    with org_context(DEFAULT_ORG_ID):
        job_id = _seed_completed_job(
            core_db, DEFAULT_ORG_ID, scorecard_status=None,
        )

    resp = client.get(f"/api/v1/translations/{job_id}/result")
    assert resp.status_code == 200, resp.text
    assert resp.json()["disposition"] is None


# ---------------------------------------------------------------------------
# (b) provenance: only real artefacts, everything else None.
# ---------------------------------------------------------------------------


def test_provenance_with_no_config_snapshot_event_is_all_none(fresh_app_client):
    """No CONFIG_SNAPSHOT_CAPTURED event for this job -> every provenance
    field is None. Specifically NOT a plausible-looking constant like
    "default", "gpt-4o", or "v1" (the exact fallback literals the legacy
    v1 audit path uses elsewhere in this codebase)."""
    client, core_db, _ = fresh_app_client
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    with org_context(DEFAULT_ORG_ID):
        job_id = _seed_completed_job(
            core_db, DEFAULT_ORG_ID, scorecard_status="PASS",
        )
        # Deliberately no v2 chain at all for this job.

    resp = client.get(f"/api/v1/translations/{job_id}/result")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["audit"] is None, "no v2 chain -> audit must be None, never a placeholder"

    provenance = data["provenance"]
    assert provenance is not None
    for field in ("model", "model_version", "prompt_version", "prompt_content_hash", "language_tier"):
        value = provenance[field]
        assert value is None, f"provenance.{field} should be None (no artefact); got {value!r}"
        assert value not in ("default", "v1", "unknown", "gpt-4o", "UNKNOWN"), (
            f"provenance.{field} looks like a plausible-looking constant: {value!r}"
        )
    # match_type IS honestly sourceable here (segments agree on "LLM").
    assert provenance["match_type"] == "LLM"


def test_provenance_model_and_prompt_fields_sourced_from_real_config_snapshot(fresh_app_client):
    """With a real CONFIG_SNAPSHOT_CAPTURED event, model/prompt_version/
    prompt_content_hash are the artefact's actual values (not a fresh live
    `resolve_model()` call, which would drift from what the job ACTUALLY
    ran with) — while model_version/language_tier (no artefact exists for
    either) stay None even though other fields ARE populated."""
    client, core_db, _ = fresh_app_client
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    with org_context(DEFAULT_ORG_ID):
        job_id = _seed_completed_job(
            core_db, DEFAULT_ORG_ID, scorecard_status="PASS",
        )
        _write_config_snapshot_event(
            core_db, DEFAULT_ORG_ID, job_id, _SAMPLE_CONFIG_SNAPSHOT,
        )

    resp = client.get(f"/api/v1/translations/{job_id}/result")
    assert resp.status_code == 200, resp.text
    provenance = resp.json()["provenance"]

    assert provenance["model"] == "gpt-4o-2024-08-06"
    assert provenance["prompt_version"] == "1.2.0"
    assert provenance["prompt_content_hash"] == "deadbeef" * 8
    # No artefact backs these two anywhere in this codebase yet.
    assert provenance["model_version"] is None
    assert provenance["language_tier"] is None


def test_provenance_model_is_a_real_string_or_none_never_a_mock_object(fresh_app_client):
    """Sanity: `model` never comes back as a non-string / non-None value —
    guards against a lazily-evaluated ORM object leaking into the response."""
    client, core_db, _ = fresh_app_client
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    with org_context(DEFAULT_ORG_ID):
        job_id = _seed_completed_job(
            core_db, DEFAULT_ORG_ID, scorecard_status="PASS",
        )
        _write_config_snapshot_event(
            core_db, DEFAULT_ORG_ID, job_id, _SAMPLE_CONFIG_SNAPSHOT,
        )

    resp = client.get(f"/api/v1/translations/{job_id}/result")
    model = resp.json()["provenance"]["model"]
    assert model is None or isinstance(model, str)


# ---------------------------------------------------------------------------
# (c) mqm MUST be None — guard against a future loop wiring the legacy
#     scorer into it.
# ---------------------------------------------------------------------------


def test_mqm_is_always_none_even_with_a_full_scorecard(fresh_app_client):
    client, core_db, _ = fresh_app_client
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    with org_context(DEFAULT_ORG_ID):
        job_id = _seed_completed_job(
            core_db, DEFAULT_ORG_ID, scorecard_status="REVIEW_REQUIRED",
        )
        _write_config_snapshot_event(
            core_db, DEFAULT_ORG_ID, job_id, _SAMPLE_CONFIG_SNAPSHOT,
        )

    resp = client.get(f"/api/v1/translations/{job_id}/result")
    assert resp.status_code == 200, resp.text
    assert resp.json()["mqm"] is None, (
        "mqm must stay None until the TMX-MQM-5b cutover — the MQM engine "
        "is shadow-only and must never be synthesized from the legacy "
        "count-based scorer (A3)."
    )


# ---------------------------------------------------------------------------
# (d) backwards compatibility — pre-existing JobResult fields unchanged.
# ---------------------------------------------------------------------------


def test_pre_existing_job_result_fields_unchanged_for_existing_caller(fresh_app_client):
    """A caller reading only the pre-TMX-SEAM-WIRE fields sees the exact
    same shape and values it always did."""
    client, core_db, _ = fresh_app_client
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID

    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    with org_context(DEFAULT_ORG_ID):
        job_id = _seed_completed_job(
            core_db, DEFAULT_ORG_ID, scorecard_status="PASS",
        )

    resp = client.get(f"/api/v1/translations/{job_id}/result")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["job_id"] == job_id
    assert data["status"] == "translated"
    assert data["original_filename"] == "doc.txt"
    assert data["translated_text"] == "Prenez 10mg par jour. Ne dépassez pas la dose."
    assert data["quality_summary"]["critical_count"] == 0
    assert data["quality_summary"]["major_count"] == 0
    assert data["quality_summary"]["minor_count"] == 0
    assert data["audit_id"] is None
    assert "completed_at" in data
    assert data["contract_version"] == "1.1.0"
