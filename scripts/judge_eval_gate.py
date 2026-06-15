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
from typing import Any, Dict, List

from app.services.judge_eval import load_judge_gold

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


def _run_judge_tier(
    gold: List[Dict[str, Any]], args: argparse.Namespace, report: Dict[str, Any]
) -> bool:
    """Run the real judge over the gold and enforce the recall/precision floor.

    Returns True on pass, False on failure. Imported lazily so structure-only
    runs (and pre-commit) never pull in the LLM stack.
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
    rel = compute_judge_reliability(planted, annotations)
    report["recall"] = rel.recall
    report["precision"] = rel.precision
    report["min_recall"] = args.min_recall
    report["min_precision"] = args.min_precision
    report["planted_total"] = rel.planted_total
    report["planted_caught"] = rel.planted_caught
    report["false_positive_segments"] = rel.false_positive_segments
    return rel.recall >= args.min_recall and rel.precision >= args.min_precision


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
    report: Dict[str, Any] = {
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

    exit_code = 0
    if args.require_judge:
        passed = _run_judge_tier(gold, args, report)
        report["result"] = "PASS" if passed else "FAIL_RECALL"
        exit_code = 0 if passed else 1
    else:
        report["result"] = "PASS_STRUCTURE_ONLY"

    _emit(report, args)
    return exit_code


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
    check.add_argument("--source-lang", default="en")
    check.add_argument("--target-lang", default="fr")
    check.add_argument("--report-json", default=None)
    return parser


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd != "check":
        build_parser().print_help()
        return 2
    return cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
