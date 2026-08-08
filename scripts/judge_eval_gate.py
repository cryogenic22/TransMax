"""
TMX-MQM-EVAL-CI — release-blocking judge-reliability gate.

The judge is a model and must be measured like one. This gate has two honest
tiers (mirroring ``.github/workflows/eval.yml``'s scope detection):

* **structure-only** (default; runs everywhere incl. pre-commit, no LLM): assert
  the gold set is present, non-empty, and has BOTH planted-Critical and clean
  cases. An empty/broken gold set fails the build — this is the guard against
  the exact vacuous-green trap where a missing gold scores recall=1.0.

* **judge** (``--require-judge``; CI only when LLM keys are present): run the
  real independent judge over the gold cases, compute recall + precision, and
  fail below EITHER floor — ``--min-recall`` (default 0.75, the headline) AND
  ``--min-precision`` (default 0.5, enforced so a flag-everything judge cannot
  pass on recall alone; tightens as the gold set grows).

Run:  ``python -m scripts.judge_eval_gate check [--require-judge] [--min-recall X]``
Exit: 0 = pass · 1 = judge below floor · 2 = gold-set integrity failure.

Reuses ``app.services.judge_eval`` (the one canonical loader + the pure
recall/precision metric) — no forked JSONL parsing, no second metric.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Mapping, Sequence

from app.services.judge_eval import (
    JudgeReliability,
    MetricDriftFinding,
    load_judge_gold,
)

_REQUIRED_KEYS = {"id", "source", "target", "planted_critical"}


def check_integrity(gold: List[Dict[str, Any]]) -> List[str]:
    """Return a list of integrity problems (empty list = healthy gold set)."""
    problems: List[str] = []
    if not gold:
        return [
            "gold set is empty or missing (an empty gold would score recall=1.0 vacuously)"
        ]
    for i, case in enumerate(gold):
        missing = _REQUIRED_KEYS - set(case)
        if missing:
            problems.append(
                f"row {i} (id={case.get('id', '?')}) missing keys: {sorted(missing)}"
            )
    if not any(c.get("planted_critical") for c in gold):
        problems.append("no planted-Critical case — recall would be vacuously 1.0")
    if not any(not c.get("planted_critical") for c in gold):
        problems.append("no clean case — precision (over-flagging) cannot be exercised")
    return problems


def _run_judge(
    gold: Sequence[Mapping[str, Any]], args: argparse.Namespace
) -> JudgeReliability:
    """Run the real independent judge over the gold set → ``JudgeReliability``.

    Imported lazily so structure-only runs (and pre-commit) never pull in the
    LLM stack. Requires LLM credentials — callers gate on key presence.
    """
    import asyncio

    from app.services.judge_eval import compute_judge_reliability
    from app.services.mqm_judge import judge_segments

    segs = [
        {
            "segment_id": c["id"],
            "source_text": c["source"],
            "translated_text": c["target"],
        }
        for c in gold
    ]
    planted = [c["id"] for c in gold if c.get("planted_critical")]
    annotations = asyncio.run(judge_segments(segs, args.source_lang, args.target_lang))
    return compute_judge_reliability(planted, annotations)


def _run_judge_tier(
    gold: Sequence[Mapping[str, Any]],
    args: argparse.Namespace,
    report: Dict[str, object],
) -> JudgeReliability:
    """Run the judge tier, fill ``report``, and return the ``JudgeReliability``.

    The pass/fail decision is left to the caller so the same run can also feed
    the drift check (TMX-MQM-EVAL-DRIFT) without a second LLM call.
    """
    rel = _run_judge(gold, args)
    report["recall"] = rel.recall
    report["precision"] = rel.precision
    report["min_recall"] = args.min_recall
    report["min_precision"] = args.min_precision
    report["planted_total"] = rel.planted_total
    report["planted_caught"] = rel.planted_caught
    report["false_positive_segments"] = rel.false_positive_segments
    return rel


# ── Drift tier (TMX-MQM-EVAL-DRIFT) ──────────────────────────────────────────


def _finding_to_dict(f: MetricDriftFinding) -> Dict[str, object]:
    return {
        "metric": f.metric,
        "current": f.current,
        "status": f.status,
        "n_history": f.n_history,
        "baseline_mean": f.baseline_mean,
        "baseline_std": f.baseline_std,
        "lower_control_limit": f.lower_control_limit,
        "reason": f.reason,
    }


def _apply_drift_check(
    current: Dict[str, float], args: argparse.Namespace, report: Dict[str, object]
) -> bool:
    """Run rolling-window drift over the current run. True if ANY metric DRIFTed.

    May raise ``json.JSONDecodeError`` on a malformed baseline — the caller turns
    that into a structured FAIL_INTEGRITY (exit 2), same contract as the gold set.
    """
    from app.services.judge_eval import detect_judge_drift, load_drift_baseline

    baseline = load_drift_baseline(args.drift_baseline)
    cfg = baseline.get("config", {})
    history = baseline.get("observations", [])
    metrics = [m for m in cfg.get("metrics", ["recall", "precision"]) if m in current]
    findings = detect_judge_drift(
        current,
        history,
        metrics=metrics,
        k=cfg.get("k", 3.0),
        min_history=cfg.get("min_history", 5),
        min_abs_drop=cfg.get("min_abs_drop", 0.05),
    )
    detected = any(f.status == "DRIFT" for f in findings.values())
    report["drift"] = {
        "history_count": len(history),
        "drift_detected": detected,
        "findings": {m: _finding_to_dict(f) for m, f in findings.items()},
    }
    return detected


def _apply_drift_structure_only(
    args: argparse.Namespace, report: Dict[str, object]
) -> None:
    """No current judge observation ⇒ drift cannot regress; just report the window."""
    from app.services.judge_eval import load_drift_baseline

    baseline = load_drift_baseline(args.drift_baseline)
    obs = baseline.get("observations", [])
    report["drift"] = {
        "status": "SKIPPED_NO_CURRENT",
        "history_count": len(obs) if isinstance(obs, list) else 0,
        "note": (
            "structure-only run has no current judge observation; drift cannot "
            "regress without a current point (defers to the absolute floor)"
        ),
    }


def _mark_drift_integrity_fail(
    report: Dict[str, object], exc: json.JSONDecodeError
) -> int:
    """Turn a malformed drift baseline into the structured FAIL_INTEGRITY / exit-2
    contract (same as a malformed gold line) rather than a raw traceback. Mutates
    ``report`` and returns 2; the single caller-side ``_emit`` prints it once."""
    report["result"] = "FAIL_INTEGRITY"
    problems = report.get("integrity_problems")
    if not isinstance(problems, list):
        problems = []
        report["integrity_problems"] = problems
    problems.append(f"drift baseline contains a malformed JSON line: {exc}")
    return 2


def _judge_and_drift(
    gold: Sequence[Mapping[str, Any]],
    args: argparse.Namespace,
    report: Dict[str, object],
) -> int:
    """Judge tier + optional drift. Returns the exit code; emitting is the caller's."""
    rel = _run_judge_tier(gold, args, report)
    passed = rel.recall >= args.min_recall and rel.precision >= args.min_precision
    report["result"] = "PASS" if passed else "FAIL_RECALL"
    exit_code = 0 if passed else 1
    if args.check_drift:
        try:
            drifted = _apply_drift_check(
                {"recall": rel.recall, "precision": rel.precision}, args, report
            )
        except json.JSONDecodeError as exc:
            return _mark_drift_integrity_fail(report, exc)
        # A drift regression blocks release; an existing recall failure (exit 1)
        # stays the headline — both are recorded in the report.
        if drifted and exit_code == 0:
            report["result"] = "FAIL_DRIFT"
            exit_code = 3
    return exit_code


def _structure_and_drift(args: argparse.Namespace, report: Dict[str, object]) -> int:
    """Structure-only tier + optional drift (which can only SKIP without a run)."""
    report["result"] = "PASS_STRUCTURE_ONLY"
    if args.check_drift:
        try:
            _apply_drift_structure_only(args, report)
        except json.JSONDecodeError as exc:
            return _mark_drift_integrity_fail(report, exc)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    try:
        gold = load_judge_gold(args.gold)
    except json.JSONDecodeError as exc:
        # A malformed gold line is an integrity failure, not a crash — keep the
        # structured FAIL_INTEGRITY / exit-2 contract instead of a raw traceback.
        _emit(
            {
                "mode": "judge" if args.require_judge else "structure-only",
                "result": "FAIL_INTEGRITY",
                "integrity_problems": [
                    f"gold set contains a malformed JSON line: {exc}"
                ],
            },
            args,
        )
        return 2
    report: Dict[str, object] = {
        "mode": "judge" if args.require_judge else "structure-only",
        "gold_count": len(gold),
        "planted_count": sum(1 for c in gold if c.get("planted_critical")),
        "clean_count": sum(1 for c in gold if not c.get("planted_critical")),
    }

    problems = check_integrity(gold)
    report["integrity_problems"] = problems
    if problems:
        report["result"] = "FAIL_INTEGRITY"
        _emit(report, args)
        return 2

    exit_code = (
        _judge_and_drift(gold, args, report)
        if args.require_judge
        else _structure_and_drift(args, report)
    )
    _emit(report, args)
    return exit_code


def _drift_update_fail(args: argparse.Namespace, **fields: object) -> int:
    """Emit a structured ``drift-update`` failure report and return exit 2."""
    _emit({"cmd": "drift-update", **fields}, args)
    return 2


def cmd_drift_update(args: argparse.Namespace) -> int:
    """Append ONE real judge observation to the drift baseline (PR-reviewed).

    This is the deliberate history-accrual path — the analogue of
    ``scripts/ratchet.py update``. It is intentionally NOT wired into CI:
    auto-appending each CI run would let a slowly-degrading judge re-center its
    own window downward (the self-rebaselining vacuous-green trap, A3).
    """
    from app.core.config import settings

    if not (
        getattr(settings, "openai_api_key", "")
        or getattr(settings, "anthropic_api_key", "")
    ):
        return _drift_update_fail(
            args,
            result="NO_KEYS",
            note="drift-update runs the real judge; set OPENAI_API_KEY or ANTHROPIC_API_KEY",
        )

    try:
        gold = load_judge_gold(args.gold)
    except json.JSONDecodeError as exc:
        return _drift_update_fail(
            args,
            result="FAIL_INTEGRITY",
            integrity_problems=[f"gold set contains a malformed JSON line: {exc}"],
        )

    problems = check_integrity(gold)
    if problems:
        return _drift_update_fail(
            args, result="FAIL_INTEGRITY", integrity_problems=problems
        )

    import pathlib

    from app.services.judge_eval import DEFAULT_DRIFT_BASELINE_PATH, load_drift_baseline

    rel = _run_judge(gold, args)
    path = (
        pathlib.Path(args.drift_baseline)
        if args.drift_baseline
        else DEFAULT_DRIFT_BASELINE_PATH
    )
    baseline = load_drift_baseline(path)
    observation = {
        "label": args.label,
        "recall": rel.recall,
        "precision": rel.precision,
        "planted_total": rel.planted_total,
        "planted_caught": rel.planted_caught,
        "false_positive_segments": rel.false_positive_segments,
    }
    baseline.setdefault("observations", []).append(observation)
    path.write_text(
        json.dumps(baseline, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    _emit(
        {
            "cmd": "drift-update",
            "result": "APPENDED",
            "observation": observation,
            "history_count": len(baseline["observations"]),
            "baseline_path": str(path),
        },
        args,
    )
    return 0


def _emit(report: Dict[str, Any], args: argparse.Namespace) -> None:
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.report_json:
        import pathlib

        p = pathlib.Path(args.report_json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="judge_eval_gate", description=__doc__)
    sub = parser.add_subparsers(dest="cmd")
    check = sub.add_parser("check", help="run the judge-reliability gate")
    check.add_argument(
        "--gold",
        default=None,
        help="path to the gold JSONL (default: the canonical set)",
    )
    check.add_argument(
        "--require-judge",
        action="store_true",
        help="run the real judge + enforce the recall floor",
    )
    check.add_argument("--min-recall", type=float, default=0.75)
    # Precision IS enforced (not a reported-only no-op): a judge that catches
    # every planted Critical by indiscriminately flagging everything must still
    # fail. 0.5 is a conservative floor for the small seed gold; it tightens as
    # the gold set grows. Recall stays the headline metric.
    check.add_argument("--min-precision", type=float, default=0.5)
    check.add_argument(
        "--check-drift",
        action="store_true",
        help="also block on rolling-window drift vs the committed baseline (exit 3)",
    )
    check.add_argument(
        "--drift-baseline",
        default=None,
        help="path to the drift baseline JSON (default: the canonical set)",
    )
    check.add_argument("--source-lang", default="en")
    check.add_argument("--target-lang", default="fr")
    check.add_argument("--report-json", default=None)

    # drift-update — deliberate, PR-reviewed history accrual (NOT wired into CI).
    upd = sub.add_parser(
        "drift-update",
        help="run the real judge once and append the observation to the drift baseline",
    )
    upd.add_argument(
        "--label", required=True, help="a run identifier for this observation"
    )
    upd.add_argument("--gold", default=None)
    upd.add_argument("--drift-baseline", default=None)
    upd.add_argument("--source-lang", default="en")
    upd.add_argument("--target-lang", default="fr")
    upd.add_argument("--report-json", default=None)
    return parser


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "check":
        return cmd_check(args)
    if args.cmd == "drift-update":
        return cmd_drift_update(args)
    build_parser().print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
