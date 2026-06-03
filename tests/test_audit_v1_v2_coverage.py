"""TMX-3110b Phase 2 — v1↔v2 audit coverage script tests.

5 tests covering:
  1. AC-1: symmetric pass (N v1 events all mirrored in v2 → pass=true, exit 0)
  2. AC-2: v2 missing an event → missing_in_v2 populated, pass=false, exit !=0
  3. AC-3: v1 missing an event → missing_in_v1 populated, pass=false, exit !=0
  4. AC-4: job has v1 only (no v2 chain) → bucketed into legacy_jobs_no_v2 (pass)
  5. AC-5/AC-7: --job-id filter narrows to a single job; --limit caps results.

Each test exercises the script via subprocess (so argparse + exit-code paths
are real), pointing it at a tmp SQLite DB seeded directly with v1/v2 rows.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "audit_v1_v2_coverage.py"


@pytest.fixture(autouse=True)
def _restore_db_bindings():
    """Isolation guard — `_init_db` rebinds the process-global
    ``app.core.database`` engine / SessionLocal / DATABASE_URL (and the
    ``DATABASE_URL`` env var) to a per-test tmp SQLite file so the schema
    is created there. Without restoring them, later tests in the full
    suite inherit a SessionLocal pointed at a now-deleted tmp file — the
    contamination that made ``test_dashboard_activity_feed`` /
    ``test_segments_element_meta`` / ``test_tamper_detection`` fail
    mid-suite while passing in isolation. Snapshot before, restore after,
    every test in this module.
    """
    import app.core.database as core_db

    saved_engine = core_db.engine
    saved_sessionlocal = core_db.SessionLocal
    saved_db_url = core_db.DATABASE_URL
    saved_env = os.environ.get("DATABASE_URL")
    try:
        yield
    finally:
        core_db.engine = saved_engine
        core_db.SessionLocal = saved_sessionlocal
        core_db.DATABASE_URL = saved_db_url
        if saved_env is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = saved_env


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_script(db_path: Path, *extra_args: str, output_dir: Path | None = None) -> tuple[int, str, str]:
    """Invoke the script with DATABASE_URL pointed at db_path. Returns (rc, stdout, stderr).

    We DO NOT chdir into output_dir; the script writes to <repo>/docs/audit-extracts/
    unless --output-dir is passed. Tests pass --output-dir to keep generated
    markdown out of the real repo.

    stdout is post-processed to strip pre-existing app/core/database.py print
    noise (e.g. "DEBUG: Using DATABASE_URL=..." and "Database tables created
    successfully.") so the JSON payload at the tail can be parsed cleanly.
    Those prints are pre-existing tech debt — not introduced by this loop.
    """
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    args = [sys.executable, str(_SCRIPT)]
    if output_dir is not None:
        args += ["--output-dir", str(output_dir)]
    args += list(extra_args)
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )
    # Strip pre-existing debug prints from app/core/database.py so the JSON
    # tail is parseable. The script itself emits a single JSON document with
    # `json.dumps(..., indent=2)` which begins with `{` — we slice from the
    # first `{` on its own line.
    out = proc.stdout
    json_start = out.find("\n{\n")
    if json_start == -1 and out.startswith("{"):
        json_start = 0
    if json_start != -1:
        out = out[json_start:].lstrip("\n")
    return proc.returncode, out, proc.stderr


def _init_db(db_path: Path) -> None:
    """Create v1 + v2 audit tables in a fresh SQLite file via the app's init_db.

    Uses the same SessionLocal-swap technique the conftest fixture uses, so
    the script's runtime path (which also reads SessionLocal at call time)
    sees the same schema.
    """
    # Set DATABASE_URL first so init_db creates tables in the right file.
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    # Force a clean reload of the engine bindings to the new URL.
    import app.core.database as core_db
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    core_db.DATABASE_URL = f"sqlite:///{db_path}"
    core_db.engine = create_engine(
        core_db.DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    core_db.SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=core_db.engine
    )
    core_db.init_db()


def _seed_org(db_path: Path, org_id: str) -> None:
    from sqlalchemy import create_engine
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    now_iso = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO organizations "
                "(id, name, slug, org_kind, is_active, created_at, updated_at) "
                "VALUES (:id, :name, :slug, 'customer', 1, :ts, :ts)"
            ).bindparams(id=org_id, name=f"org-{org_id[:8]}", slug=f"org-{org_id[:8]}", ts=now_iso)
        )
    engine.dispose()


def _seed_v1_chain(db_path: Path, org_id: str, job_id: str, event_types: list[str]) -> str:
    """Seed an AuditRecord + N AuditLogEntry rows for job_id. Returns audit_id."""
    from sqlalchemy import create_engine
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    audit_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    with engine.begin() as conn:
        # translation_jobs_queue FK row
        conn.execute(
            text(
                "INSERT OR IGNORE INTO translation_jobs_queue "
                "(job_id, organization_id, request_id, status, "
                "source_language, target_language, request_json, "
                "is_deleted, created_at) "
                "VALUES (:job, :org, :req, 'PENDING', 'en', 'es', '{}', 0, :ts)"
            ).bindparams(job=job_id, org=org_id, req=f"req-{job_id[:8]}", ts=now_iso)
        )
        # AuditRecord
        conn.execute(
            text(
                "INSERT INTO audit_records_queue "
                "(audit_id, organization_id, job_id, created_at, is_deleted) "
                "VALUES (:aid, :org, :job, :ts, 0)"
            ).bindparams(aid=audit_id, org=org_id, job=job_id, ts=now_iso)
        )
        # AuditLogEntry rows
        prev_hash = "GENESIS_HASH"
        for idx, etype in enumerate(event_types):
            payload = {"event": etype, "idx": idx}
            entry_hash = hashlib.sha256(
                f"{prev_hash}{json.dumps(payload, sort_keys=True)}".encode()
            ).hexdigest()
            conn.execute(
                text(
                    "INSERT INTO audit_log_entries "
                    "(entry_id, organization_id, audit_id, sequence_index, "
                    "event_type, payload, previous_hash, entry_hash, "
                    "timestamp, is_deleted) "
                    "VALUES (:eid, :org, :aid, :seq, :et, :payload, "
                    ":prev, :hash, :ts, 0)"
                ).bindparams(
                    eid=str(uuid.uuid4()),
                    org=org_id,
                    aid=audit_id,
                    seq=idx,
                    et=etype,
                    payload=json.dumps(payload),
                    prev=prev_hash,
                    hash=entry_hash,
                    ts=now_iso,
                )
            )
            prev_hash = entry_hash
    engine.dispose()
    return audit_id


def _seed_v2_chain(db_path: Path, org_id: str, job_id: str, event_types: list[str]) -> None:
    """Seed translation_jobs row + N AuditEventV2 rows for job_id."""
    from sqlalchemy import create_engine
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    src_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        # translation_jobs FK target (regulatory layer)
        conn.execute(
            text(
                "INSERT OR IGNORE INTO translation_jobs "
                "(id, source_document_id, organization_id, source_language, "
                "target_language, provider, is_deleted, created_at) "
                "VALUES (:id, :src, :org, 'en', 'es', 'OPENAI', 0, :ts)"
            ).bindparams(id=job_id, src=src_id, org=org_id, ts=now_iso)
        )
        prev_hash = b"\x00" * 32
        for idx, etype in enumerate(event_types):
            # Spec-canonical hashes not required for THIS test — coverage
            # script never recomputes them; it only counts presence.
            event_hash = hashlib.sha256(f"v2:{etype}:{idx}".encode()).digest()
            payload_hash = hashlib.sha256(f"v2payload:{etype}:{idx}".encode()).digest()
            conn.execute(
                text(
                    "INSERT INTO audit_events_v2 "
                    "(event_id, organization_id, job_id, sequence_index, "
                    "domain_tag, event_type, actor_id, actor_kind, payload, "
                    "payload_hash, previous_hash, event_hash, event_ts_utc, "
                    "tsa_token, created_at) "
                    "VALUES (:eid, :org, :job, :seq, :tag, :et, NULL, "
                    "'system', :payload, :ph, :prev, :h, :ts, NULL, :ts)"
                ).bindparams(
                    eid=str(uuid.uuid4()),
                    org=org_id,
                    job=job_id,
                    seq=idx,
                    tag="transmax.audit.v1",
                    et=etype,
                    payload=json.dumps({"event": etype, "idx": idx}),
                    ph=payload_hash,
                    prev=prev_hash,
                    h=event_hash,
                    ts=now_iso,
                )
            )
            prev_hash = event_hash
    engine.dispose()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_ac1_symmetric_pass(tmp_path: Path) -> None:
    """AC-1: N v1 events mirrored in v2 → pass=true, exit 0."""
    db = tmp_path / "audit.db"
    _init_db(db)
    org = "00000000-0000-0000-0000-000000000001"
    _seed_org(db, org)
    job = str(uuid.uuid4())
    events = ["AUDIT_TRAIL_INITIALIZED", "CONFIG_SNAPSHOT_CAPTURED", "JOB_STARTED"]
    _seed_v1_chain(db, org, job, events)
    _seed_v2_chain(db, org, job, events)

    out_dir = tmp_path / "audit-extracts"
    rc, stdout, stderr = _run_script(db, output_dir=out_dir)
    assert rc == 0, f"expected exit 0, got {rc}; stderr={stderr}; stdout={stdout}"

    report = json.loads(stdout)
    jobs = {j["job_id"]: j for j in report["jobs"]}
    assert job in jobs, f"job {job} not in report: {list(jobs.keys())}"
    entry = jobs[job]
    assert entry["pass"] is True
    assert entry["v1_count"] == 3
    assert entry["v2_count"] == 3
    assert entry["missing_in_v2"] == []
    assert entry["missing_in_v1"] == []
    assert report["legacy_jobs_no_v2"] == []
    assert report["summary"]["jobs_fail"] == 0


def test_ac2_missing_in_v2_detected(tmp_path: Path) -> None:
    """AC-2: v2 missing one event → missing_in_v2 populated, pass=false, exit !=0."""
    db = tmp_path / "audit.db"
    _init_db(db)
    org = "00000000-0000-0000-0000-000000000001"
    _seed_org(db, org)
    job = str(uuid.uuid4())
    v1_events = ["AUDIT_TRAIL_INITIALIZED", "CONFIG_SNAPSHOT_CAPTURED", "JOB_STARTED"]
    v2_events = ["AUDIT_TRAIL_INITIALIZED", "JOB_STARTED"]  # CONFIG_SNAPSHOT_CAPTURED dropped
    _seed_v1_chain(db, org, job, v1_events)
    _seed_v2_chain(db, org, job, v2_events)

    out_dir = tmp_path / "audit-extracts"
    rc, stdout, _stderr = _run_script(db, output_dir=out_dir)
    assert rc != 0, "expected non-zero exit when a job fails"

    report = json.loads(stdout)
    entry = next(j for j in report["jobs"] if j["job_id"] == job)
    assert entry["pass"] is False
    assert entry["v1_count"] == 3
    assert entry["v2_count"] == 2
    assert len(entry["missing_in_v2"]) == 1
    miss = entry["missing_in_v2"][0]
    assert miss["event_type"] == "CONFIG_SNAPSHOT_CAPTURED"
    assert "v1_sequence_index" in miss
    assert "timestamp" in miss
    assert entry["missing_in_v1"] == []


def test_ac3_missing_in_v1_detected(tmp_path: Path) -> None:
    """AC-3: v2 has an event v1 doesn't → missing_in_v1 populated, pass=false."""
    db = tmp_path / "audit.db"
    _init_db(db)
    org = "00000000-0000-0000-0000-000000000001"
    _seed_org(db, org)
    job = str(uuid.uuid4())
    v1_events = ["AUDIT_TRAIL_INITIALIZED", "JOB_STARTED"]
    v2_events = ["AUDIT_TRAIL_INITIALIZED", "JOB_STARTED", "PHANTOM_EVENT"]  # extra
    _seed_v1_chain(db, org, job, v1_events)
    _seed_v2_chain(db, org, job, v2_events)

    out_dir = tmp_path / "audit-extracts"
    rc, stdout, _stderr = _run_script(db, output_dir=out_dir)
    assert rc != 0

    report = json.loads(stdout)
    entry = next(j for j in report["jobs"] if j["job_id"] == job)
    assert entry["pass"] is False
    assert len(entry["missing_in_v1"]) == 1
    miss = entry["missing_in_v1"][0]
    assert miss["event_type"] == "PHANTOM_EVENT"
    assert "v2_sequence_index" in miss
    assert entry["missing_in_v2"] == []


def test_ac4_legacy_jobs_no_v2_bucket(tmp_path: Path) -> None:
    """AC-4: a job with only v1 (no v2) goes into legacy bucket, PASSes by definition."""
    db = tmp_path / "audit.db"
    _init_db(db)
    org = "00000000-0000-0000-0000-000000000001"
    _seed_org(db, org)
    job = str(uuid.uuid4())
    _seed_v1_chain(db, org, job, ["JOB_STARTED", "JOB_FINALIZED"])
    # No v2 chain.

    out_dir = tmp_path / "audit-extracts"
    rc, stdout, _stderr = _run_script(db, output_dir=out_dir)
    assert rc == 0, "legacy jobs with no v2 chain are PASS — should be exit 0"

    report = json.loads(stdout)
    legacy = report["legacy_jobs_no_v2"]
    assert len(legacy) == 1
    assert legacy[0]["job_id"] == job
    assert legacy[0]["v1_count"] == 2
    # And the job is NOT listed in the regular jobs array (legacy is its own bucket).
    assert not any(j["job_id"] == job for j in report["jobs"])


def test_ac5_ac7_job_id_filter_and_limit_and_markdown(tmp_path: Path) -> None:
    """AC-5 (exit codes), AC-6 (markdown), AC-7 (--job-id, --limit) together."""
    db = tmp_path / "audit.db"
    _init_db(db)
    org = "00000000-0000-0000-0000-000000000001"
    _seed_org(db, org)

    # Job A: symmetric (pass)
    job_a = str(uuid.uuid4())
    _seed_v1_chain(db, org, job_a, ["JOB_STARTED"])
    _seed_v2_chain(db, org, job_a, ["JOB_STARTED"])

    # Job B: failing (v2 missing event)
    job_b = str(uuid.uuid4())
    _seed_v1_chain(db, org, job_b, ["JOB_STARTED", "JOB_FINALIZED"])
    _seed_v2_chain(db, org, job_b, ["JOB_STARTED"])

    out_dir = tmp_path / "audit-extracts"

    # --job-id filter on the PASSING job → exit 0, only that job in report
    rc, stdout, _stderr = _run_script(db, "--job-id", job_a, output_dir=out_dir)
    assert rc == 0
    report = json.loads(stdout)
    job_ids_in_report = [j["job_id"] for j in report["jobs"]] + [
        j["job_id"] for j in report["legacy_jobs_no_v2"]
    ]
    assert job_a in job_ids_in_report
    assert job_b not in job_ids_in_report

    # --job-id filter on the FAILING job → exit !=0
    rc, stdout, _stderr = _run_script(db, "--job-id", job_b, output_dir=out_dir)
    assert rc != 0
    report = json.loads(stdout)
    assert any(j["job_id"] == job_b and j["pass"] is False for j in report["jobs"])

    # --limit 1: only one job in the report (deterministic ordering)
    rc, stdout, _stderr = _run_script(db, "--limit", "1", output_dir=out_dir)
    report = json.loads(stdout)
    job_count = len(report["jobs"]) + len(report["legacy_jobs_no_v2"])
    assert job_count == 1, f"expected 1 job under --limit 1; got {job_count}"

    # AC-6: markdown summary exists in --output-dir
    today = date.today().isoformat()
    md_path = out_dir / f"v1-v2-coverage-{today}.md"
    assert md_path.exists(), f"expected markdown file at {md_path}"
    md = md_path.read_text(encoding="utf-8")
    # Match the markdown title (script renders "v1-v2 audit coverage — <date>").
    assert "v1-v2 audit coverage" in md
    assert "Per-job table" in md
