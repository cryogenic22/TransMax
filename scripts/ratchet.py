#!/usr/bin/env python3
"""
TransMax Ratchet — monotonic-improvement quality gate.

Per Karpathy's recommendation: the bar only moves up. Once we fix a class
of debt, we add a check that prevents regression. Every metric is either:

  - a "bad" metric that ratchets DOWN (lower is better, capped at baseline)
  - a "good" metric that ratchets UP (higher is better, floored at baseline)

Pre-commit (and CI) re-measures every metric and fails if any regressed.
You may *only* lower a baseline — never raise it without explicit PR review.

Usage:
    python scripts/ratchet.py status     # show current vs baseline as a table
    python scripts/ratchet.py check      # CI / pre-commit mode — fail on regression
    python scripts/ratchet.py measure    # print current measurements as JSON
    python scripts/ratchet.py update     # write new baseline (PR-reviewed)

Exit codes:
    0 — all metrics OK (current ≤ baseline for bad, ≥ baseline for good)
    1 — at least one metric regressed
    2 — usage / measurement error

Pure stdlib. No pip install required.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# Force UTF-8 stdout/stderr so the glyphs below render on Windows cp1252.
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

# ── Layout ──────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = REPO_ROOT / "ratchet" / "baseline.json"

# Directories scanned for backend metrics
BACKEND_ROOTS = ("app", "scripts", "tests", "transmax_sdk", "transmax_mcp")

# Directories scanned for frontend metrics
FRONTEND_ROOTS = ("frontend/app", "frontend/components", "frontend/hooks", "frontend/lib")

# Globs we always exclude from any scan
EXCLUDES = (
    "**/__pycache__/**",
    "**/.pytest_cache/**",
    "**/node_modules/**",
    "**/.next/**",
    "**/.venv/**",
    "**/venv/**",
    "**/dist/**",
    "**/build/**",
    "**/.git/**",
    "**/.quality-reports/**",
    # Vendored quality-gate is upstream code, not transmax
    "quality-gate/**",
    # Alembic auto-generated mega-migration is treated as legacy
    "alembic/versions/**",
    # Frontend test fixtures + node helpers
    "frontend/__tests__/__fixtures__/**",
)


# ── Metric model ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Metric:
    name: str
    direction: Literal["down", "up"]
    description: str
    measure: Callable[[], int]


# ── File walking ────────────────────────────────────────────────────────


def _excluded(path: Path) -> bool:
    """Whether `path` matches any exclude glob (relative to REPO_ROOT)."""
    rel = path.relative_to(REPO_ROOT)
    rel_str = rel.as_posix()
    for pattern in EXCLUDES:
        if rel.match(pattern) or rel_str.startswith(pattern.replace("/**", "")):
            return True
    return False


def _iter_files(roots: Iterable[str], suffixes: tuple[str, ...]) -> Iterable[Path]:
    """Yield files under `roots` matching one of `suffixes`, excluding EXCLUDES."""
    for root in roots:
        rp = REPO_ROOT / root
        if not rp.exists():
            continue
        for path in rp.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in suffixes:
                continue
            if _excluded(path):
                continue
            yield path


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# ── Measurement primitives ──────────────────────────────────────────────


def _count_pattern(roots: Iterable[str], suffixes: tuple[str, ...], pattern: re.Pattern[str]) -> int:
    total = 0
    for f in _iter_files(roots, suffixes):
        total += len(pattern.findall(_read(f)))
    return total


def _count_files_matching(globs: Iterable[str]) -> int:
    seen: set[Path] = set()
    for pattern in globs:
        for path in REPO_ROOT.glob(pattern):
            if path.is_file() and not _excluded(path):
                seen.add(path)
    return len(seen)


def _count_files_by_size(roots: Iterable[str], suffixes: tuple[str, ...], min_lines: int) -> int:
    total = 0
    for f in _iter_files(roots, suffixes):
        try:
            n = sum(1 for _ in f.open(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if n >= min_lines:
            total += 1
    return total


def _count_test_functions() -> int:
    pattern = re.compile(r"^\s*(?:async\s+)?def\s+test_\w+\s*\(", re.MULTILINE)
    total = 0
    for f in _iter_files(("tests",), (".py",)):
        total += len(pattern.findall(_read(f)))
    return total


def _count_test_files() -> int:
    return sum(1 for f in _iter_files(("tests",), (".py",)) if f.name.startswith("test_"))


# ── Backend regex metrics ───────────────────────────────────────────────

# Match `# type: ignore` but allow `# type: ignore[import-not-found]` (legitimate per quality-gate config).
RX_TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore(?!\[import-not-found\])", re.IGNORECASE)

# Bare `except:` (no exception class). The negative lookahead avoids matching `except SpecificError:`.
RX_BARE_EXCEPT = re.compile(r"^\s*except\s*:", re.MULTILINE)

# `print(` outside scripts/ and tests/ — app/ should use logger.
RX_PRINT_IN_APP = re.compile(r"^\s*print\s*\(", re.MULTILINE)

# `Any` annotations
RX_ANY = re.compile(r":\s*Any\b|->\s*Any\b|\bList\[Any\]|\bDict\[[^,]+,\s*Any\]|\bOptional\[Any\]")

# Deferred-work markers without an issue link `(#NNN)` per the quality-gate config.
# Keyword list is constructed (not inlined) so this meter does not trip itself —
# without this trick the regex source line would itself match the regex, inflating
# the count by 1 per keyword and turning the metric into a self-referential mess.
_TODO_KEYWORDS = ("T" + "ODO", "FIX" + "ME", "X" + "XX", "HA" + "CK", "B" + "UG")
RX_TODO_BARE = re.compile(
    r"\b(?:" + "|".join(_TODO_KEYWORDS) + r")(?!\s*\(#\d+\))",
    re.IGNORECASE,
)

# Placeholder strings the May 2026 review flagged — should reach 0.
# Match only when the string appears as an assignment value (`= "..."`) or a
# dict value (`: "..."`), not when it's enumerated in a detection set
# (e.g. INSECURE_SECRET_KEYS in app/core/config.py).
RX_PLACEHOLDER = re.compile(
    r'(?:=|:)\s*["\'](?:placeholder_hash|change-me-in-production|change_this_unsafe_secret)["\']'
)


# ── Frontend regex metrics ──────────────────────────────────────────────

RX_AS_ANY = re.compile(r"\bas\s+any\b")
RX_TS_IGNORE = re.compile(r"//\s*@ts-ignore|/\*\s*@ts-ignore\s*\*/")
RX_TS_NOCHECK = re.compile(r"//\s*@ts-nocheck|/\*\s*@ts-nocheck\s*\*/")
# console.log/debug/trace — but not console.error / .warn / .info (per quality-gate exceptions).
RX_CONSOLE_LOG = re.compile(r"\bconsole\.(log|debug|trace)\s*\(")
# `: any` and `<any>` in TS/TSX (ignoring strings in JSX)
RX_TS_ANY = re.compile(r":\s*any\b|<any>|\bArray<any>|\bRecord<[^,]+,\s*any>")


# ── Metric registry ─────────────────────────────────────────────────────


METRICS: list[Metric] = [
    # ── Backend "bad" metrics (down) ────────────────────────────────────
    Metric(
        "backend.type_ignore",
        "down",
        "`# type: ignore` comments in app/scripts/tests (excludes import-not-found).",
        lambda: _count_pattern(BACKEND_ROOTS, (".py",), RX_TYPE_IGNORE),
    ),
    Metric(
        "backend.bare_except",
        "down",
        "`except:` with no exception class — silent error swallow.",
        lambda: _count_pattern(BACKEND_ROOTS, (".py",), RX_BARE_EXCEPT),
    ),
    Metric(
        "backend.print_in_app",
        "down",
        "`print(` calls in app/ (use logger instead). Scripts and tests are exempt.",
        lambda: _count_pattern(("app",), (".py",), RX_PRINT_IN_APP),
    ),
    Metric(
        "backend.any_annotations",
        "down",
        "`Any` type annotations — defeats the type system.",
        lambda: _count_pattern(BACKEND_ROOTS, (".py",), RX_ANY),
    ),
    Metric(
        # Name composed at import time so the bare keyword does not appear as a
        # word in this file's source (see _TODO_KEYWORDS rationale above).
        f"backend.{_TODO_KEYWORDS[0].lower()}_without_issue",
        "down",
        "Deferred-work markers (see _TODO_KEYWORDS) without an issue link `(#NNN)`.",
        lambda: _count_pattern(BACKEND_ROOTS + ("frontend/app", "frontend/components", "frontend/lib"), (".py", ".ts", ".tsx", ".js", ".jsx"), RX_TODO_BARE),
    ),
    Metric(
        "backend.placeholder_strings",
        "down",
        "Known placeholder strings flagged by the May 2026 review (placeholder_hash, change-me-in-production, change_this_unsafe_secret).",
        lambda: _count_pattern(BACKEND_ROOTS, (".py",), RX_PLACEHOLDER),
    ),
    Metric(
        "backend.mega_files_800",
        "down",
        "Backend files ≥ 800 lines — refactor candidates per quality-gate `file_size`.",
        lambda: _count_files_by_size(BACKEND_ROOTS, (".py",), 800),
    ),
    # ── Frontend "bad" metrics (down) ───────────────────────────────────
    Metric(
        "frontend.as_any",
        "down",
        "`as any` casts in TS/TSX.",
        lambda: _count_pattern(FRONTEND_ROOTS, (".ts", ".tsx"), RX_AS_ANY),
    ),
    Metric(
        "frontend.ts_ignore",
        "down",
        "`// @ts-ignore` comments.",
        lambda: _count_pattern(FRONTEND_ROOTS, (".ts", ".tsx"), RX_TS_IGNORE),
    ),
    Metric(
        "frontend.ts_nocheck",
        "down",
        "`// @ts-nocheck` directives.",
        lambda: _count_pattern(FRONTEND_ROOTS, (".ts", ".tsx"), RX_TS_NOCHECK),
    ),
    Metric(
        "frontend.console_log",
        "down",
        "`console.log/debug/trace` calls — production code uses structured logging or sonner toasts.",
        lambda: _count_pattern(FRONTEND_ROOTS, (".ts", ".tsx"), RX_CONSOLE_LOG),
    ),
    Metric(
        "frontend.any_annotations",
        "down",
        "Explicit `: any` / `<any>` / `Array<any>` annotations.",
        lambda: _count_pattern(FRONTEND_ROOTS, (".ts", ".tsx"), RX_TS_ANY),
    ),
    # ── Repo hygiene "bad" metrics (down) ───────────────────────────────
    Metric(
        "hygiene.committed_db_files",
        "down",
        "`*.db` files committed at or under the repo root (May 2026 review C-01-adjacent).",
        lambda: _count_files_matching(("*.db", "**/*.db")),
    ),
    Metric(
        "hygiene.committed_log_files",
        "down",
        "`*.log` files committed at or under the repo root.",
        lambda: _count_files_matching(("*.log", "**/*.log")),
    ),
    Metric(
        "hygiene.committed_pyc_files",
        "down",
        "`*.pyc` files committed.",
        lambda: _count_files_matching(("**/*.pyc",)),
    ),
    # ── "Good" metrics (up) ─────────────────────────────────────────────
    Metric(
        "tests.functions",
        "up",
        "Total `test_*` function count under tests/.",
        _count_test_functions,
    ),
    Metric(
        "tests.files",
        "up",
        "Total test_*.py file count under tests/.",
        _count_test_files,
    ),
]


METRIC_INDEX = {m.name: m for m in METRICS}


# ── Baseline I/O ────────────────────────────────────────────────────────


def load_baseline() -> dict[str, int]:
    if not BASELINE_PATH.exists():
        return {}
    try:
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("metrics", {})
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: failed to read baseline {BASELINE_PATH}: {exc}", file=sys.stderr)
        sys.exit(2)


def write_baseline(measurements: dict[str, int], note: str | None = None) -> None:
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "$schema": "ratchet/schema.json",
        "description": (
            "Monotonic-improvement baseline. Every metric is either 'bad' "
            "(direction: down — current must be <= baseline) or 'good' "
            "(direction: up — current must be >= baseline). Update only via "
            "`python scripts/ratchet.py update` and PR review."
        ),
        "directions": {m.name: m.direction for m in METRICS},
        "metrics": measurements,
        "note": note or "",
    }
    BASELINE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# ── Commands ────────────────────────────────────────────────────────────


def measure_all() -> dict[str, int]:
    return {m.name: m.measure() for m in METRICS}


def cmd_measure(_args: argparse.Namespace) -> int:
    print(json.dumps(measure_all(), indent=2, sort_keys=True))
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    baseline = load_baseline()
    current = measure_all()
    name_w = max(len(m.name) for m in METRICS)
    print(f"{'metric':<{name_w}}  {'dir':>4}  {'baseline':>10}  {'current':>10}  status")
    print("-" * (name_w + 50))
    any_red = False
    for m in METRICS:
        b = baseline.get(m.name, "—")
        c = current.get(m.name, 0)
        if b == "—":
            status = "(no baseline)"
        elif m.direction == "down":
            if c > b:
                status = "❌ REGRESSED"
                any_red = True
            elif c < b:
                status = "✅ improved"
            else:
                status = "✅ ok"
        else:  # up
            if c < b:
                status = "❌ REGRESSED"
                any_red = True
            elif c > b:
                status = "✅ improved"
            else:
                status = "✅ ok"
        print(f"{m.name:<{name_w}}  {m.direction:>4}  {b!s:>10}  {c!s:>10}  {status}")
    print()
    if any_red:
        print("Some metrics regressed. Run `python scripts/ratchet.py check` for the failure summary.")
    return 0


def cmd_check(_args: argparse.Namespace) -> int:
    baseline = load_baseline()
    if not baseline:
        print("error: no baseline at ratchet/baseline.json. Run `python scripts/ratchet.py update`.", file=sys.stderr)
        return 2
    current = measure_all()
    failures: list[str] = []
    for m in METRICS:
        b = baseline.get(m.name)
        if b is None:
            continue  # baseline doesn't track this metric (e.g. metric added after baseline)
        c = current[m.name]
        if m.direction == "down" and c > b:
            failures.append(
                f"{m.name}: current {c} > baseline {b} (delta +{c - b}). "
                f"{m.description}"
            )
        elif m.direction == "up" and c < b:
            failures.append(
                f"{m.name}: current {c} < baseline {b} (delta {c - b}). "
                f"{m.description}"
            )
    if failures:
        print("RATCHET REGRESSION — the following metrics got worse:")
        print()
        for f in failures:
            print(f"  ❌ {f}")
        print()
        print("Either fix the regression, or — if intentional — update the baseline:")
        print("  python scripts/ratchet.py update")
        print()
        print("Baselines should typically only get TIGHTER, not looser. Loosening is a")
        print("PR-reviewed exception, not a routine update.")
        return 1
    print(f"✓ Ratchet OK — all {len(METRICS)} metrics at or better than baseline.")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    current = measure_all()
    if BASELINE_PATH.exists():
        old = load_baseline()
        # Refuse to loosen "down" metrics or tighten "up" metrics without --force
        loosening: list[str] = []
        for m in METRICS:
            if m.name not in old:
                continue
            o = old[m.name]
            n = current[m.name]
            if m.direction == "down" and n > o:
                loosening.append(f"{m.name}: {o} → {n} (+{n - o})")
            elif m.direction == "up" and n < o:
                loosening.append(f"{m.name}: {o} → {n} ({n - o})")
        if loosening and not args.force:
            print("REFUSING to loosen the baseline. The following metrics regressed:")
            print()
            for line in loosening:
                print(f"  ⚠ {line}")
            print()
            print("If this loosening is intentional (e.g. you removed a generated file from the repo,")
            print("inflating a count temporarily), pass --force AND describe why in --note.")
            return 1
    note = args.note or ""
    write_baseline(current, note=note)
    print(f"✓ Baseline updated at {BASELINE_PATH.relative_to(REPO_ROOT)}")
    print()
    print("Tracked metrics:")
    for m in METRICS:
        print(f"  {m.name:<35} = {current[m.name]:>6}  ({m.direction})")
    return 0


# ── CLI ─────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Show current vs baseline as a table.")
    sub.add_parser("check", help="CI / pre-commit mode — fail on regression.")
    sub.add_parser("measure", help="Print current measurements as JSON.")

    p_update = sub.add_parser("update", help="Write new baseline (PR-reviewed).")
    p_update.add_argument("--force", action="store_true", help="Allow loosening (regressions in baseline).")
    p_update.add_argument("--note", default="", help="One-line note describing why the baseline was updated.")

    args = parser.parse_args()
    handlers = {
        "status": cmd_status,
        "check": cmd_check,
        "measure": cmd_measure,
        "update": cmd_update,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
