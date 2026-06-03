#!/usr/bin/env python3
"""TMX-3110b — Phase 2 v1↔v2 audit coverage script.

Compares the legacy v1 audit chain (`AuditLogEntry` linked via
`AuditRecord.job_id`) against the new v2 chain (`AuditEventV2` for the
same `job_id`). Per job_id, reports:

    - events in v1 but missing from v2 (TMX-3110 Phase 1's broad-except
      may have silently dropped one — this script catches that)
    - events in v2 but missing from v1 (shouldn't happen until Phase 3
      callers start writing v2-only)
    - per-event-type counts on both sides
    - per-job pass/fail (PASS iff both missing-sets are empty)

Output: JSON to stdout, plus a markdown summary to
`docs/audit-extracts/v1-v2-coverage-<DATE>.md`. Exit code is non-zero if
any non-legacy job fails (covers AC-5).

Bridge between v1 and v2: both `AuditRecord.job_id`
(operational-layer translation_jobs_queue) and `AuditEventV2.job_id`
(regulatory-layer translation_jobs) hold the SAME string value — the
graph nodes (TMX-3110 Phase 1) double-write with `state['job_id']` to
both writers, and the regulatory job row is seeded with the same id.

Multiset semantics: a job may legitimately have multiple events of the
same type if it ran twice. We compare `Counter(v1_types)` against
`Counter(v2_types)` so duplicates are counted, not collapsed.

Why standalone CLI (not a verifier extension or dashboard endpoint):
the canonical Phase 2 operator triage path runs offline. TMX-3104's
verifier is within-v2 only by design; mixing scopes would obscure both.
This script is also intended to run from a future scheduled cron
(TMX-3110b-cron, spawn-candidate).

Usage:
  python scripts/audit_v1_v2_coverage.py
  python scripts/audit_v1_v2_coverage.py --job-id <uuid>
  python scripts/audit_v1_v2_coverage.py --limit 20
  python scripts/audit_v1_v2_coverage.py --output-dir <path>

Exit codes:
  0 — every non-legacy job has full coverage parity.
  1 — at least one non-legacy job has missing_in_v2 or missing_in_v1.
  2 — environmental error (DB not initialised, args invalid).

A1 (audit-by-default) + A10 (program brain): the script is the
operator-facing self-instrumentation that surfaces v2 coverage gaps the
within-v2 verifier cannot see by construction.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

# Allow imports from the repo root when invoked as `python scripts/...`.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:  # pragma: no cover - script-style runtime
    sys.path.insert(0, str(_REPO_ROOT))


def _reconfigure_stdout_utf8() -> None:
    """Make stdout/stderr tolerate non-ASCII on cp1252 Windows consoles."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


# ---------------------------------------------------------------------------
# Data classes (plain dicts to keep JSON serialisation trivial)
# ---------------------------------------------------------------------------


def _v1_events_for_job(session, job_id: str) -> list[dict[str, Any]]:
    """Return v1 events for job_id ordered by (audit_id, sequence_index).

    Joins AuditRecord -> AuditLogEntry via audit_id. A job MAY have
    multiple AuditRecord rows (e.g. if create_audit_trail was called
    twice across reruns). We flatten across all of them and keep the
    per-record sequence_index for diagnostic value.
    """
    from app.models.models import AuditLogEntry, AuditRecord

    rows = (
        session.query(AuditLogEntry, AuditRecord)
        .join(AuditRecord, AuditLogEntry.audit_id == AuditRecord.audit_id)
        .filter(AuditRecord.job_id == job_id)
        # Admin/forensic path per app/models/tenant_scoped.py:87 — this is a
        # cross-tenant coverage audit; bypass the per-tenant filter.
        .execution_options(include_other_tenants=True)
        .order_by(AuditRecord.created_at, AuditLogEntry.sequence_index)
        .all()
    )
    out: list[dict[str, Any]] = []
    for entry, _record in rows:
        out.append(
            {
                "event_type": entry.event_type,
                "sequence_index": entry.sequence_index,
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                "audit_id": entry.audit_id,
            }
        )
    return out


def _v2_events_for_job(session, job_id: str) -> list[dict[str, Any]]:
    """Return v2 events for job_id ordered by sequence_index."""
    from app.models.audit_v2 import AuditEventV2

    rows = (
        session.query(AuditEventV2)
        .filter(AuditEventV2.job_id == job_id)
        .execution_options(include_other_tenants=True)
        .order_by(AuditEventV2.sequence_index)
        .all()
    )
    out: list[dict[str, Any]] = []
    for ev in rows:
        out.append(
            {
                "event_type": ev.event_type,
                "sequence_index": ev.sequence_index,
                "timestamp": ev.event_ts_utc.isoformat() if ev.event_ts_utc else None,
            }
        )
    return out


def _diff_v1_missing_in_v2(
    v1_events: list[dict[str, Any]], v2_events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return the v1 events whose event_type appears MORE times in v1 than v2.

    Multiset semantics: if v1 has 2× JOB_STARTED and v2 has 1×, the
    'extra' v1 occurrence (the LAST one in v1-order) is reported. We
    report at most (v1_count - v2_count) entries per event_type.
    """
    v1_counter = Counter(e["event_type"] for e in v1_events)
    v2_counter = Counter(e["event_type"] for e in v2_events)
    missing: list[dict[str, Any]] = []
    for etype, v1_n in v1_counter.items():
        v2_n = v2_counter.get(etype, 0)
        if v1_n > v2_n:
            # Pick the LAST (v1_n - v2_n) v1 occurrences of this type;
            # the first v2_n occurrences are taken to be "mirrored".
            occurrences = [e for e in v1_events if e["event_type"] == etype]
            for occ in occurrences[v2_n:]:
                missing.append(
                    {
                        "event_type": etype,
                        "v1_sequence_index": occ["sequence_index"],
                        "timestamp": occ["timestamp"],
                    }
                )
    # Sort for deterministic output (event_type then v1_sequence_index).
    missing.sort(key=lambda m: (m["event_type"], m["v1_sequence_index"]))
    return missing


def _diff_v2_missing_in_v1(
    v1_events: list[dict[str, Any]], v2_events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Reverse of _diff_v1_missing_in_v2."""
    v1_counter = Counter(e["event_type"] for e in v1_events)
    v2_counter = Counter(e["event_type"] for e in v2_events)
    missing: list[dict[str, Any]] = []
    for etype, v2_n in v2_counter.items():
        v1_n = v1_counter.get(etype, 0)
        if v2_n > v1_n:
            occurrences = [e for e in v2_events if e["event_type"] == etype]
            for occ in occurrences[v1_n:]:
                missing.append(
                    {
                        "event_type": etype,
                        "v2_sequence_index": occ["sequence_index"],
                        "timestamp": occ["timestamp"],
                    }
                )
    missing.sort(key=lambda m: (m["event_type"], m["v2_sequence_index"]))
    return missing


# ---------------------------------------------------------------------------
# Main coverage computation
# ---------------------------------------------------------------------------


def compute_coverage(
    session, job_filter: str | None = None, limit: int | None = None
) -> dict[str, Any]:
    """Compute the full coverage report.

    Returns a dict shaped:
        {
          "generated_at": ISO8601,
          "jobs": [ {job_id, v1_count, v2_count, missing_in_v2, missing_in_v1,
                     v1_event_type_counts, v2_event_type_counts, pass}, ... ],
          "legacy_jobs_no_v2": [ {job_id, v1_count}, ... ],
          "summary": { totals... },
        }
    """
    from app.models.models import AuditRecord
    from app.models.audit_v2 import AuditEventV2

    # Collect distinct job_ids on each side.
    v1_job_rows = (
        session.query(AuditRecord.job_id)
        .filter(AuditRecord.job_id.isnot(None))
        .execution_options(include_other_tenants=True)
        .distinct()
        .all()
    )
    v2_job_rows = (
        session.query(AuditEventV2.job_id)
        .execution_options(include_other_tenants=True)
        .distinct()
        .all()
    )

    v1_jobs = {row[0] for row in v1_job_rows if row[0]}
    v2_jobs = {row[0] for row in v2_job_rows if row[0]}
    all_jobs = sorted(v1_jobs | v2_jobs)

    if job_filter is not None:
        all_jobs = [j for j in all_jobs if j == job_filter]
    if limit is not None:
        all_jobs = all_jobs[:limit]

    jobs_report: list[dict[str, Any]] = []
    legacy_jobs: list[dict[str, Any]] = []

    total_v1 = 0
    total_v2 = 0
    total_missing_in_v2 = 0
    total_missing_in_v1 = 0
    jobs_pass = 0
    jobs_fail = 0

    for job_id in all_jobs:
        v1_events = _v1_events_for_job(session, job_id)
        v2_events = _v2_events_for_job(session, job_id)

        total_v1 += len(v1_events)
        total_v2 += len(v2_events)

        if len(v2_events) == 0 and len(v1_events) > 0:
            legacy_jobs.append({"job_id": job_id, "v1_count": len(v1_events)})
            jobs_pass += 1  # legacy is PASS by definition (AC-4)
            continue

        missing_in_v2 = _diff_v1_missing_in_v2(v1_events, v2_events)
        missing_in_v1 = _diff_v2_missing_in_v1(v1_events, v2_events)
        total_missing_in_v2 += len(missing_in_v2)
        total_missing_in_v1 += len(missing_in_v1)

        ok = not missing_in_v2 and not missing_in_v1
        if ok:
            jobs_pass += 1
        else:
            jobs_fail += 1

        jobs_report.append(
            {
                "job_id": job_id,
                "v1_count": len(v1_events),
                "v2_count": len(v2_events),
                "missing_in_v2": missing_in_v2,
                "missing_in_v1": missing_in_v1,
                "v1_event_type_counts": dict(
                    Counter(e["event_type"] for e in v1_events)
                ),
                "v2_event_type_counts": dict(
                    Counter(e["event_type"] for e in v2_events)
                ),
                "pass": ok,
            }
        )

    summary = {
        "total_jobs": len(jobs_report) + len(legacy_jobs),
        "jobs_pass": jobs_pass,
        "jobs_fail": jobs_fail,
        "legacy_jobs_no_v2_count": len(legacy_jobs),
        "total_v1_events": total_v1,
        "total_v2_events": total_v2,
        "total_missing_in_v2": total_missing_in_v2,
        "total_missing_in_v1": total_missing_in_v1,
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "jobs": jobs_report,
        "legacy_jobs_no_v2": legacy_jobs,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def render_markdown(report: dict[str, Any]) -> str:
    """Render a markdown summary for docs/audit-extracts/."""
    today = date.today().isoformat()
    lines: list[str] = []
    lines.append(f"# v1-v2 audit coverage — {today}")
    lines.append("")
    lines.append(f"_Generated:_ `{report['generated_at']}`")
    lines.append("")
    lines.append("## Summary")
    s = report["summary"]
    lines.append(f"- Total jobs scanned: **{s['total_jobs']}**")
    lines.append(f"- Jobs PASS: **{s['jobs_pass']}**")
    lines.append(f"- Jobs FAIL: **{s['jobs_fail']}**")
    lines.append(
        f"- Legacy jobs (v1 only, no v2 chain — TMX-3109 migration targets): "
        f"**{s['legacy_jobs_no_v2_count']}**"
    )
    lines.append(f"- Total v1 events: {s['total_v1_events']}")
    lines.append(f"- Total v2 events: {s['total_v2_events']}")
    lines.append(f"- Missing in v2 (across all jobs): {s['total_missing_in_v2']}")
    lines.append(f"- Missing in v1 (across all jobs): {s['total_missing_in_v1']}")
    lines.append("")

    lines.append("## Per-job table")
    lines.append("")
    lines.append("| job_id | v1 count | v2 count | missing_in_v2 | missing_in_v1 | verdict |")
    lines.append("|---|---|---|---|---|---|")
    for j in report["jobs"]:
        verdict = "PASS" if j["pass"] else "**FAIL**"
        miss_v2 = (
            ", ".join(m["event_type"] for m in j["missing_in_v2"][:3])
            + ("..." if len(j["missing_in_v2"]) > 3 else "")
            if j["missing_in_v2"]
            else "—"
        )
        miss_v1 = (
            ", ".join(m["event_type"] for m in j["missing_in_v1"][:3])
            + ("..." if len(j["missing_in_v1"]) > 3 else "")
            if j["missing_in_v1"]
            else "—"
        )
        lines.append(
            f"| `{j['job_id']}` | {j['v1_count']} | {j['v2_count']} | "
            f"{miss_v2} | {miss_v1} | {verdict} |"
        )
    if not report["jobs"]:
        lines.append("| _(no jobs with both v1 and v2 chains)_ | | | | | |")
    lines.append("")

    if report["legacy_jobs_no_v2"]:
        lines.append("## Legacy jobs (v1 only — pre-Phase-1)")
        lines.append("")
        lines.append("| job_id | v1 count |")
        lines.append("|---|---|")
        for j in report["legacy_jobs_no_v2"]:
            lines.append(f"| `{j['job_id']}` | {j['v1_count']} |")
        lines.append("")
        lines.append(
            "These jobs predate TMX-3110 Phase 1 (commit `a23b0eb`). They are"
            " PASS by definition for coverage purposes; target them with the"
            " historical migration script when TMX-3109 ships."
        )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "_Source: `scripts/audit_v1_v2_coverage.py` (TMX-3110b). Within-v2 hash "
        "integrity is verified separately by TMX-3104 (`app/services/"
        "audit_verifier_v2.py`)._"
    )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _build_session():
    """Open a SessionLocal from app.core.database, reading it at call time.

    Reading SessionLocal at call time matches the writer-singleton thunk
    pattern in `app/agents/_audit_v2_emit.py:_get_audit_writer_v2`. This
    keeps the script honest if DATABASE_URL has been swapped externally
    (e.g. by a test fixture that swapped engine in-place).
    """
    from app.core.database import SessionLocal
    return SessionLocal()


def main(argv: list[str] | None = None) -> int:
    _reconfigure_stdout_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--job-id",
        type=str,
        default=None,
        help="Restrict the report to a single job_id (default: all jobs).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap the number of jobs scanned (sampling mode).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_REPO_ROOT / "docs" / "audit-extracts",
        help="Directory for the markdown summary (default: docs/audit-extracts/).",
    )
    args = parser.parse_args(argv)

    try:
        session = _build_session()
    except Exception as exc:  # noqa: BLE001 — entrypoint diagnostic
        print(f"error: could not open DB session: {exc}", file=sys.stderr)
        return 2

    try:
        report = compute_coverage(
            session, job_filter=args.job_id, limit=args.limit
        )
    finally:
        session.close()

    # Emit JSON to stdout (canonical machine-readable output).
    print(json.dumps(report, indent=2, default=str))

    # Write markdown to <output-dir>/v1-v2-coverage-<DATE>.md.
    args.output_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    md_path = args.output_dir / f"v1-v2-coverage-{today}.md"
    md_path.write_text(render_markdown(report), encoding="utf-8")

    # Exit code per AC-5: non-zero if any non-legacy job failed.
    if report["summary"]["jobs_fail"] > 0:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - script entrypoint
    sys.exit(main())
