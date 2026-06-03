"""Standalone runner for the AI eval harness.

Used by CI (`.github/workflows/eval.yml`) and by `make eval`. Equivalent to
running pytest on `tests/evals/` but emits a JSON report compatible with the
headless-spec eval surface (per-suite pass/fail summary).

Usage:
    python -m tests.evals.runner --report-json eval_results/latest.json
    python -m tests.evals.runner --scope harness-only

Exit codes:
    0 — all cases passed
    1 — at least one case failed
    2 — runner / setup error
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path
from typing import Any

# Force UTF-8 stdout/stderr for Windows compatibility.
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EVAL_DATA_DIR = REPO_ROOT / "tests" / "evals" / "data"


def _load_suite(jsonl_path: Path) -> list[dict[str, Any]]:
    with jsonl_path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _run_suite(jsonl_path: Path, target_lang: str, source_lang: str = "en") -> dict[str, Any]:
    """Run one suite (one JSONL file) and return a structured result."""
    from app.services.quality_gate import QualityGateService

    qg = QualityGateService()
    cases = _load_suite(jsonl_path)
    failures: list[dict[str, Any]] = []
    passed = 0
    for case in cases:
        defects = qg.check_segment(
            source_text=case["source"],
            target_text=case["target"],
            constraints={"glossary": [], "tm_matches": []},
            target_lang=target_lang,
            source_lang=source_lang,
        )
        actual = sorted(
            d["category"] for d in defects if d.get("severity") == "CRITICAL"
        )
        expected = sorted(
            e["category"] for e in case.get("expected_defects", []) if e.get("severity") == "CRITICAL"
        )
        if case["kind"] == "canonical":
            if actual:
                failures.append({
                    "id": case["id"],
                    "reason": f"canonical produced unexpected CRITICAL defects: {actual}",
                    "rationale": case.get("rationale", ""),
                })
                continue
        elif case["kind"] == "tampered":
            missed = [e for e in expected if e not in actual]
            if missed:
                failures.append({
                    "id": case["id"],
                    "reason": f"tampered missed expected CRITICAL defects: {missed} (got {actual})",
                    "rationale": case.get("rationale", ""),
                })
                continue
        passed += 1

    return {
        "suite": str(jsonl_path.relative_to(REPO_ROOT).as_posix()),
        "language_pair": f"{source_lang}-{target_lang}",
        "total": len(cases),
        "passed": passed,
        "failed": len(failures),
        "failures": failures,
    }


# Suite registry: (path, source_lang, target_lang). Add new suites here.
SUITES: list[tuple[str, str, str]] = [
    ("data/en_es/critical_safety.jsonl", "en", "es"),
]


def run_all(scope: str) -> dict[str, Any]:
    started_at = time.time()
    suites_data: list[dict[str, Any]] = []
    total = 0
    passed = 0
    failed = 0
    skipped = 0
    failures: list[dict[str, Any]] = []

    for rel_path, src, tgt in SUITES:
        jsonl_path = EVAL_DATA_DIR / Path(rel_path).relative_to("data")
        if not jsonl_path.exists():
            skipped += 1
            continue

        # In `harness-only` scope we run the deterministic gates suite (no LLM).
        # In `full` scope we'd also run live-LLM golden suites under tests/evals/live/
        # — those are deferred until v3.0 epic E7.9 lands.
        suite_result = _run_suite(jsonl_path, target_lang=tgt, source_lang=src)
        suites_data.append(suite_result)
        total += suite_result["total"]
        passed += suite_result["passed"]
        failed += suite_result["failed"]
        for f in suite_result["failures"]:
            failures.append({**f, "suite": suite_result["suite"]})

    return {
        "scope": scope,
        "started_at": started_at,
        "duration_seconds": round(time.time() - started_at, 3),
        "suites": suites_data,
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scope", choices=["harness-only", "full"], default="harness-only",
                   help="Eval scope. 'harness-only' runs the deterministic gates suites; 'full' adds live-LLM suites (deferred until v3.0 E7.9).")
    p.add_argument("--report-json", type=Path, default=None, help="Write a JSON report to this path.")
    args = p.parse_args(argv)

    report = run_all(args.scope)

    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote report: {args.report_json}")

    print(f"\nEval suites: {len(report['suites'])} run, {report['skipped']} skipped")
    print(f"Cases: {report['passed']}/{report['total']} passed ({report['failed']} failed)")
    if report["failures"]:
        print("\nFailures:")
        for f in report["failures"]:
            print(f"  [{f['suite']}] {f['id']}: {f['reason']}")
            if f.get("rationale"):
                print(f"    rationale: {f['rationale']}")

    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
