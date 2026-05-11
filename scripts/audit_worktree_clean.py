#!/usr/bin/env python3
"""Audit drift between the local working tree and ``origin/main``.

Sister to ``scripts/audit_worksheet_drift.py``: that script catches drift
between WORKSHEET headers and the commit graph. THIS script catches drift
between the WORKING TREE and the committed code on ``origin/main``.

The recurring failure mode this prevents: a local worktree silently reverts
an invariant (e.g. re-introduces ``DEFAULT_ORG_ID`` literals that TMX-3012d
shipped a test to prevent) and the 4-agent verification audit then reports
those reds as a regression, when in fact they are pure worktree drift. The
4-agent audit shouldn't have to triage worktree state — that's this script's
job.

Scope (intentionally narrow):

  - Only checks files under ``app/`` and ``tests/``. Other paths (frontend/,
    docs/, .context/, etc.) are out of scope: they have their own drift gates
    (worksheet audit, frontend snapshot audit, etc.).
  - Compares working-tree-vs-``origin/main`` content. Files that are
    *committed locally but not yet pushed* are NOT flagged — those are
    legitimate ahead-of-remote state caught by ``audit_worksheet_drift.py``.
  - ADVISORY by default: prints findings and exits non-zero, but is hooked
    into ``.pre-commit-config.yaml`` as advisory (``always_run: true`` with
    ``verbose: true``) so it surfaces without blocking emergency commits.

Exit codes:
  0 — no drift, or only legitimate in-flight tracked changes that match
      what ``git status`` already shows.
  1 — drift detected: a file's working-tree content differs from
      ``origin/main`` AND the difference is NOT also present in HEAD
      (i.e. the local edit reverts shipped code without the developer
      having committed the revert).
  2 — git or filesystem error.

Usage:
  python scripts/audit_worktree_clean.py
  python scripts/audit_worktree_clean.py --root /path/to/repo
  python scripts/audit_worktree_clean.py --remote-ref origin/main
  python scripts/audit_worktree_clean.py --paths app/ tests/

Why this matters (TMX-CORRECTIVE-20260511 lesson):
  The 2026-05-11 verify-audit flagged 53 reds. ~43 were stale-DB false reds
  (TMX-3002 territory). Two were dirty-worktree false reds — a local revert
  of TMX-3012c that no commit ever shipped. Without this script, the next
  audit will re-discover that drift by running the test suite, which is
  slow and noisy. This script answers the question in one git diff.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run_git(args: list[str], cwd: Path) -> tuple[int, str]:
    """Run a git subcommand. Returns (exit_code, stdout). stderr suppressed."""
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return proc.returncode, proc.stdout


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


def list_tracked_files(repo_root: Path, path_prefixes: list[str]) -> list[str]:
    """List git-tracked files under the given path prefixes."""
    args = ["ls-files", "--", *path_prefixes]
    code, out = _run_git(args, repo_root)
    if code != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def file_differs_vs_ref(repo_root: Path, file_path: str, ref: str) -> bool:
    """Return True iff the working-tree file content differs from ref's blob.

    Uses ``git diff --quiet`` which returns:
      0 = no difference
      1 = difference
      other = error (treated as no-difference to avoid false alarms).
    """
    code, _ = _run_git(["diff", "--quiet", ref, "--", file_path], repo_root)
    return code == 1


def file_differs_vs_head(repo_root: Path, file_path: str) -> bool:
    """Return True iff the working-tree file content differs from HEAD's blob."""
    code, _ = _run_git(["diff", "--quiet", "HEAD", "--", file_path], repo_root)
    return code == 1


def main() -> int:
    _reconfigure_stdout_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root (default: parent of scripts/).",
    )
    parser.add_argument(
        "--remote-ref",
        default="origin/main",
        help="Remote ref to compare against (default: origin/main).",
    )
    parser.add_argument(
        "--paths",
        nargs="+",
        default=["app/", "tests/"],
        help="Path prefixes to check (default: app/ tests/).",
    )
    parser.add_argument(
        "--include-pyc",
        action="store_true",
        help="Include .pyc files (default: skip — they're build artefacts).",
    )
    args = parser.parse_args()

    repo_root: Path = args.root
    if not (repo_root / ".git").exists():
        print(f"error: {repo_root} is not a git repository", file=sys.stderr)
        return 2

    # Verify remote ref resolves.
    code, _ = _run_git(["rev-parse", "--verify", args.remote_ref], repo_root)
    if code != 0:
        print(
            f"error: {args.remote_ref} does not resolve. Run `git fetch` first.",
            file=sys.stderr,
        )
        return 2

    tracked = list_tracked_files(repo_root, args.paths)
    if not tracked:
        print(f"No tracked files under {args.paths}; nothing to check.")
        return 0

    drift_files: list[str] = []
    in_flight_files: list[str] = []

    for file_path in tracked:
        # Skip build artefacts unless explicitly requested.
        if not args.include_pyc and (
            file_path.endswith(".pyc") or "__pycache__" in file_path
        ):
            continue

        differs_remote = file_differs_vs_ref(repo_root, file_path, args.remote_ref)
        if not differs_remote:
            continue  # working tree matches remote — no drift.

        differs_head = file_differs_vs_head(repo_root, file_path)
        if differs_head:
            # Working tree differs from HEAD too — the developer has an
            # in-progress local edit. That's legitimate worktree state;
            # report but don't fail.
            in_flight_files.append(file_path)
        else:
            # Working tree matches HEAD but HEAD differs from remote — this is
            # a legitimate ahead-of-remote commit, caught by the worksheet
            # drift audit, not this one. Skip.
            #
            # OR: working tree differs from remote AND matches HEAD — same
            # case; skip. (differs_remote=True + differs_head=False means
            # HEAD differs from remote in a way the worktree mirrors.)
            continue

    # Report.
    print("# Worktree drift audit")
    print(f"_remote ref:_ `{args.remote_ref}`")
    print(f"_paths:_ {args.paths}")
    print()

    if in_flight_files:
        print(f"## In-flight local edits (advisory) — {len(in_flight_files)}")
        print()
        print(
            "These files have working-tree edits that differ from both HEAD "
            "and `origin/main`. They may be legitimate in-progress work, OR "
            "they may be a silent revert of shipped code. Check each one."
        )
        print()
        for fp in in_flight_files:
            print(f"  - {fp}")
        print()
        # In-flight is legitimate enough that we treat it as advisory only
        # at the script level. The pre-commit hook can decide whether to
        # block; the script just surfaces.
        drift_files.extend(in_flight_files)

    if not drift_files:
        print("Working tree clean vs origin/main for the requested paths.")
        return 0

    print(
        f"DRIFT ADVISORY: {len(drift_files)} file(s) have working-tree content "
        f"that differs from `{args.remote_ref}` AND from HEAD."
    )
    print(
        "  If these edits are intentional in-progress work, commit them with "
        "a ticket id. If they are an unintended revert of shipped code, run "
        "`git checkout HEAD -- <file>` to restore."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
