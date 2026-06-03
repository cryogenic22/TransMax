"""
TMX-3202 — Real model + prompt version + content-hash in the JobConfigSnapshot.

The pre-fix `validate_request` node hard-coded the config snapshot's system
block as `{"model": "gpt-4o", "prompts_version": "v1.0"}` — a placeholder that
(a) is not the configured model and (b) does not match the on-disk prompt
registry version. That violates A6 (LLM = qualified supplier: record the real
model + prompt version) and A8 (pin every prompt to a version).

These tests assert the captured JobConfigSnapshot for a job contains:
  - the REAL model string from settings (NOT the literal "gpt-4o" placeholder),
  - the real prompt version + content_hash for each pinned agent, matching what
    PromptRegistry returns,
  - and that the prior `prompts_version: "v1.0"` placeholder is gone.

RED before the graph.py fix lands, GREEN after.

Fixtures mirror tests/test_tmx_3110_double_write.py (the sibling audit loop):
same fresh-engine + downstream-SessionLocal-rebind pattern so the v1 audit
path through DatabaseService picks up the test engine.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker


# ---------------------------------------------------------------------------
# Fixtures (mirrored from test_tmx_3110_double_write.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_db_with_org(fresh_engine_for_db, monkeypatch):
    """Fresh SQLite engine + active org context, with downstream SessionLocal
    bindings re-pointed at the fresh engine for the v1 audit path."""
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID
    import app.models.database as mdb
    import app.services.db_service as dbs

    core_db = fresh_engine_for_db
    monkeypatch.setattr(mdb, "SessionLocal", core_db.SessionLocal, raising=True)
    monkeypatch.setattr(mdb, "engine", core_db.engine, raising=True)
    monkeypatch.setattr(dbs, "SessionLocal", core_db.SessionLocal, raising=True)
    monkeypatch.setattr(dbs, "engine", core_db.engine, raising=True)

    dbs.DatabaseService._instance = None
    dbs.DatabaseService._initialized = False

    Session = sessionmaker(bind=core_db.engine)
    session = Session()
    with org_context(DEFAULT_ORG_ID):
        yield core_db, session
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
                id=org_id, name=f"org-{org_id[:8]}", slug=f"org-{org_id[:8]}", ts=now_iso
            )
        )


def _seed_job(engine, org_id: str) -> str:
    """Seed both job rows so v1 (queue) + v2 (regulatory) FKs are satisfiable."""
    job_id = str(uuid.uuid4())
    src_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO translation_jobs_queue "
                "(job_id, organization_id, request_id, status, "
                "source_language, target_language, request_json, "
                "is_deleted, created_at) "
                "VALUES (:job, :org, :req, 'PENDING', 'en', 'es', "
                "'{}', 0, :ts)"
            ).bindparams(job=job_id, org=org_id, req=f"req-{job_id[:8]}", ts=now_iso)
        )
        conn.execute(
            text(
                "INSERT INTO translation_jobs "
                "(id, source_document_id, organization_id, source_language, "
                "target_language, provider, is_deleted, created_at) "
                "VALUES (:id, :src, :org, 'en', 'es', 'OPENAI', 0, :ts)"
            ).bindparams(id=job_id, src=src_id, org=org_id, ts=now_iso)
        )
    return job_id


def _seed_document(engine, doc_id: str, org_id: str) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO documents (id, organization_id, name, "
                "source_language, status, is_deleted, created_at, updated_at) "
                "VALUES (:id, :org, 'test.txt', 'en', 'UPLOADED', 0, :ts, :ts)"
            ).bindparams(id=doc_id, org=org_id, ts=now_iso)
        )


def _run_validate(graph_mod, job_id: str, doc_id: str) -> None:
    """Reset singletons to the fresh engine and run validate_request."""
    from app.agents import _audit_v2_emit as v2_emit_mod

    v2_emit_mod.reset_writer_singleton_for_test()
    graph_mod._db_service = None
    graph_mod._audit_service = None

    state: dict = {
        "doc_id": doc_id,
        "job_id": job_id,
        "target_language": "es",
        "source_language": "en",
        "iteration_count": 0,
        "segments": [],
        "constraint_pack": {},
        "quality_report": {},
        "error": None,
    }
    asyncio.run(graph_mod.validate_request(state))


def _load_snapshot_config(session, job_id: str) -> dict:
    from app.models.models import JobConfigSnapshot

    snap = session.query(JobConfigSnapshot).filter_by(job_id=job_id).one()
    return snap.config_json


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_snapshot_records_real_model_not_placeholder(fresh_db_with_org):
    """AC-1/AC-3: the captured snapshot's system.model is the configured model
    from settings, and is NOT the literal "gpt-4o" placeholder."""
    from app.agents import graph as graph_mod
    from app.core.config import settings
    from app.models.database import DEFAULT_ORG_ID

    core_db, session = fresh_db_with_org
    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    doc_id = str(uuid.uuid4())
    _seed_document(core_db.engine, doc_id, DEFAULT_ORG_ID)

    _run_validate(graph_mod, job_id, doc_id)

    config = _load_snapshot_config(session, job_id)
    assert config["system"]["model"] == settings.default_gpt_model
    # Guard: the configured default is not the old placeholder, and the
    # snapshot must not silently carry it.
    assert config["system"]["model"] != "gpt-4o"


def test_snapshot_records_real_prompt_versions_and_hashes(fresh_db_with_org):
    """AC-2: each pinned agent's prompt version + content_hash in the snapshot
    matches exactly what PromptRegistry resolves, and the placeholder
    `prompts_version: "v1.0"` field is gone."""
    from app.agents import graph as graph_mod
    from app.agents.prompts import PromptRegistry
    from app.models.database import DEFAULT_ORG_ID

    core_db, session = fresh_db_with_org
    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    doc_id = str(uuid.uuid4())
    _seed_document(core_db.engine, doc_id, DEFAULT_ORG_ID)

    _run_validate(graph_mod, job_id, doc_id)

    config = _load_snapshot_config(session, job_id)
    system = config["system"]

    # Placeholder field removed.
    assert "prompts_version" not in system

    prompts = system["prompts"]
    for agent in ("translator", "fixer", "reviewer"):
        loaded = PromptRegistry.load(agent)
        assert prompts[agent]["version"] == loaded.version
        assert prompts[agent]["content_hash"] == loaded.content_hash
        # A8: never the bare "v1.0" placeholder; a real semver.
        assert prompts[agent]["version"] != "v1.0"
        # content_hash is a real SHA-256 hex digest.
        assert len(prompts[agent]["content_hash"]) == 64


def test_snapshot_request_block_preserved(fresh_db_with_org):
    """AC-4 (regression): the request block still carries doc_id / target_language
    / job_id exactly as before — the fix is additive on the system block only."""
    from app.agents import graph as graph_mod
    from app.models.database import DEFAULT_ORG_ID

    core_db, session = fresh_db_with_org
    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    doc_id = str(uuid.uuid4())
    _seed_document(core_db.engine, doc_id, DEFAULT_ORG_ID)

    _run_validate(graph_mod, job_id, doc_id)

    config = _load_snapshot_config(session, job_id)
    assert config["request"]["doc_id"] == doc_id
    assert config["request"]["target_language"] == "es"
    assert config["request"]["job_id"] == job_id


def test_v2_config_snapshot_event_matches_v1(fresh_db_with_org):
    """AC-5: the TMX-3110 v2 CONFIG_SNAPSHOT_CAPTURED event carries the SAME
    real model + prompt provenance as the v1 snapshot — the fix must not let the
    two chains diverge (the v2 emit reuses the same dict)."""
    from app.agents import graph as graph_mod
    from app.core.config import settings
    from app.models.audit_v2 import AuditEventV2
    from app.models.database import DEFAULT_ORG_ID

    core_db, session = fresh_db_with_org
    _seed_org(core_db.engine, DEFAULT_ORG_ID)
    job_id = _seed_job(core_db.engine, DEFAULT_ORG_ID)
    doc_id = str(uuid.uuid4())
    _seed_document(core_db.engine, doc_id, DEFAULT_ORG_ID)

    _run_validate(graph_mod, job_id, doc_id)

    event = (
        session.query(AuditEventV2)
        .filter_by(job_id=job_id, event_type="CONFIG_SNAPSHOT_CAPTURED")
        .one()
    )
    payload = event.payload
    assert payload["system"]["model"] == settings.default_gpt_model
    assert payload["system"]["model"] != "gpt-4o"
    assert "prompts_version" not in payload["system"]
    assert "translator" in payload["system"]["prompts"]
