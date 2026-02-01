#!/usr/bin/env python3
"""
Quality Gate - Portable Code Quality Enforcement System
========================================================
Drop this into any codebase for instant quality enforcement.

Usage:
    python quality_gate.py                    # Check all files
    python quality_gate.py --staged           # Check staged files only (for pre-commit)
    python quality_gate.py --report           # Generate detailed report
    python quality_gate.py --strict           # Fail on warnings too
    python quality_gate.py --min-score 90     # Enforce stricter PRS threshold
    python quality_gate.py --no-prs           # Disable PRS scoring gate
    python quality_gate.py path/to/file.py    # Check specific file

Exit codes:
    0 - All checks passed
    1 - Errors found (blocks commit/merge)
    2 - Warnings found (--strict mode only)
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import subprocess
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from qg.autofix import apply_deterministic_fixes
from qg.checks_complexity import check_max_complexity
from qg.checks_debug import check_no_debug_statements
from qg.checks_duplicates import check_duplicate_helpers
from qg.checks_imports import check_import_boundaries, check_import_count
from qg.checks_safety import check_no_hardcoded_secrets, check_no_silent_catch
from qg.checks_size import check_file_size, check_function_size
from qg.checks_tests_smells import (
    check_classvar_in_tests,
    check_duplicate_class_defs,
    check_noqa_ann001,
    check_test_parametrisation,
)
from qg.checks_text import check_no_todo_fixme, check_no_type_escape
from qg.context import RuleContext
from qg.path_glob import matches_any, normalize_rel_path
from qg.rules_ai_engineering import apply as apply_ai_engineering_rules
from qg.rules_evals import apply as apply_eval_rules
from qg.rules_governance import apply as apply_governance_rules
from qg.rules_phase1 import apply as apply_phase1_rules
from qg.rules_phase2 import apply as apply_phase2_rules
from qg.rules_tests import apply as apply_test_rules
from qg.types import CheckResult, Issue, Severity, parse_severity
from qg.coaching import coaching_suggestion

DEFAULT_CONFIG: dict[str, Any] = {
    "paths": {
        "include": [],
        "extensions": [".py", ".ts", ".tsx", ".js", ".jsx"],
        "exclude": [
            "**/node_modules/**",
            "**/dist/**",
            "**/build/**",
            "**/.next/**",
            "**/.git/**",
            "**/__pycache__/**",
            "**/.pytest_cache/**",
            "**/.venv/**",
            "**/.venv*/**",
            "**/venv/**",
            "**/venv*/**",
            "**/site-packages/**",
            "**/.quality-reports/**",
            "**/coverage/**",
        ],
    },
    "rules": {
        "file_size": {"enabled": True, "max_lines": 800, "warning_lines": 500, "severity": "error"},
        "function_size": {"enabled": True, "max_lines": 50, "severity": "error"},
        "no_todo_fixme": {"enabled": True, "severity": "error"},
        "no_debug_statements": {"enabled": True, "severity": "warning"},
        "no_type_escape": {"enabled": True, "severity": "warning"},
        "no_silent_catch": {"enabled": True, "severity": "error"},
    },
    "prs": {
        "enabled": True,
        "min_score": 85,
        "error_weight": 10,
        "warning_weight": 2,
        "_note": "PRS = 100 - (errors*10) - (warnings*2).",
    },
    "thresholds": {"error_count": 0},
}

_PACK_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = dict(base)
    for k, v in override.items():
        existing = out.get(k)
        if isinstance(v, dict) and isinstance(existing, dict):
            out[k] = _deep_merge(existing, v)
        else:
            out[k] = v
    return out


def _find_git_root(start: Path) -> Path | None:
    p = start.resolve()
    for parent in [p, *p.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def _git_cmd(git_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", f"safe.directory={git_root}", "-C", str(git_root), *args],
        capture_output=True,
        text=True,
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _pack_paths(*, script_dir: Path, pack_names: list[str]) -> list[Path]:
    packs_dir = script_dir / "packs"
    if not pack_names:
        return []
    out: list[Path] = []
    packs_root = packs_dir.resolve()
    for raw in pack_names:
        name = str(raw).strip()
        if not name:
            continue
        if not _PACK_NAME_RE.match(name):
            continue
        candidate = (packs_root / f"{name}.json").resolve()
        try:
            candidate.relative_to(packs_root)
        except ValueError:
            continue
        if candidate.exists():
            out.append(candidate)
    return out


def _config_sources(*, script_dir: Path, root_dir: Path, config_path: str | None) -> list[Path]:
    sources: list[Path] = []
    defaults_path = script_dir / "quality-gate.config.json"
    if defaults_path.exists():
        sources.append(defaults_path)
    root_override = root_dir / ".quality-gate.json"
    if root_override.exists():
        sources.append(root_override)
    root_config = root_dir / "quality-gate.config.json"
    if root_config.exists():
        sources.append(root_config)
    if config_path:
        p = Path(config_path)
        if p.exists():
            sources.append(p)
    return sources


def _load_config(
    *, script_dir: Path, root_dir: Path, config_path: str | None
) -> tuple[dict[str, Any], list[Path]]:
    base_sources = _config_sources(
        script_dir=script_dir, root_dir=root_dir, config_path=config_path
    )

    early: dict[str, Any] = dict(DEFAULT_CONFIG)
    for src in base_sources:
        early = _deep_merge(early, _read_json(src))

    packs = early.get("packs", [])
    pack_names = [str(p) for p in packs] if isinstance(packs, list) else []
    pack_sources = _pack_paths(script_dir=script_dir, pack_names=pack_names)

    final_sources: list[Path] = []
    defaults_path = script_dir / "quality-gate.config.json"
    if defaults_path.exists():
        final_sources.append(defaults_path)
    final_sources.extend(pack_sources)
    for src in base_sources:
        if src == defaults_path:
            continue
        final_sources.append(src)

    merged: dict[str, Any] = dict(DEFAULT_CONFIG)
    for src in final_sources:
        merged = _deep_merge(merged, _read_json(src))
    return merged, final_sources


class QualityGate:
    def __init__(
        self, config_path: str | None = None, root_dir: str | None = None, *, quiet: bool = False
    ):
        script_dir = Path(__file__).resolve().parent
        default_root = script_dir.parent
        self.root_dir = Path(root_dir).resolve() if root_dir else default_root
        self.git_root = _find_git_root(self.root_dir) or _find_git_root(Path.cwd())
        self._quiet = quiet

        self.config, self._config_sources = _load_config(
            script_dir=script_dir, root_dir=self.root_dir, config_path=config_path
        )

        self.issues: list[Issue] = []
        self.stats: dict[str, int] = defaultdict(int)
        self.file_prs: dict[str, dict[str, Any]] = {}

        if not self._quiet:
            self._print_config_sources()

    def _print_config_sources(self) -> None:
        if not self._config_sources:
            print("[QualityGate] No config found, using defaults")
            return
        print("[QualityGate] Config sources:")
        for src in self._config_sources:
            print(f"  - {src}")

    def _rel_path(self, file: str | Path) -> str:
        with contextlib.suppress(ValueError):
            return os.path.relpath(str(file), str(self.root_dir)).replace("\\", "/")
        return normalize_rel_path(str(file))

    def _add_issue(
        self,
        *,
        file: str | Path,
        line: int,
        rule: str,
        severity: Severity | str,
        message: str,
        column: int = 0,
        snippet: str = "",
        suggestion: str = "",
    ) -> None:
        suggestion_text = str(suggestion).strip() or coaching_suggestion(str(rule))
        self.issues.append(
            Issue(
                file=self._rel_path(file),
                line=int(line),
                column=int(column),
                rule=str(rule),
                severity=parse_severity(severity, default=Severity.WARNING),
                message=str(message),
                code_snippet=str(snippet),
                suggestion=suggestion_text,
            )
        )
        sev = self.issues[-1].severity
        self.stats[sev.value] += 1
        self.stats[f"{sev.value}_{rule}"] += 1

    def _mk_add_issue_for_file(self, file_path: Path) -> Callable[..., None]:
        def _add(**kwargs: Any) -> None:
            file_arg = kwargs.pop("file", file_path)
            self._add_issue(file=file_arg, **kwargs)

        return _add

    def _get_language(self, file_path: Path) -> str:
        ext = file_path.suffix.lower()
        return {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
        }.get(ext, "unknown")

    @staticmethod
    def _is_test_path(file_path: Path) -> bool:
        rel = str(file_path).replace("\\", "/").lower()
        name = file_path.name.lower()
        if any(token in rel for token in ("/tests/", "/test/")):
            return True
        if any(rel.startswith(prefix) for prefix in ("tests/", "test/")):
            return True
        if name.startswith("test_") or name.endswith("_test.py"):
            return True
        return any(
            name.endswith(suffix)
            for suffix in (
                ".spec.ts",
                ".spec.tsx",
                ".test.ts",
                ".test.tsx",
                ".spec.js",
                ".test.js",
            )
        )

    def _is_code_file(self, file_path: Path) -> bool:
        exts = self.config.get("paths", {}).get("extensions", [".py", ".ts", ".tsx", ".js", ".jsx"])
        ext_set = {str(e).lower() for e in (exts or [])} if isinstance(exts, list) else set()
        if not ext_set:
            ext_set = {".py", ".ts", ".tsx", ".js", ".jsx"}
        return file_path.suffix.lower() in ext_set

    def _should_check_file(self, file_path: Path, *, explicit: bool = False) -> bool:
        rel = self._rel_path(file_path)
        paths_cfg = (
            self.config.get("paths", {}) if isinstance(self.config.get("paths", {}), dict) else {}
        )
        excludes = [str(p) for p in (paths_cfg.get("exclude", []) or [])]
        if excludes and matches_any(rel, excludes):
            return False

        includes = [str(p) for p in (paths_cfg.get("include", []) or [])]
        if explicit or not includes:
            return True
        return matches_any(rel, includes)

    def _safe_is_file(self, file_path: Path) -> bool:
        with contextlib.suppress(OSError, ValueError):
            return file_path.is_file()
        return False

    def _safe_exists(self, path: Path) -> bool:
        with contextlib.suppress(OSError, ValueError):
            return path.exists()
        return False

    def _safe_is_dir(self, path: Path) -> bool:
        with contextlib.suppress(OSError, ValueError):
            return path.is_dir()
        return False

    def get_files_to_check(self, paths: list[str] | None, staged_only: bool) -> list[Path]:
        if staged_only:
            return self._files_from_staged()
        if paths:
            return self._files_from_paths(paths)
        files = self._files_from_git_ls()
        return files if files else self._files_from_walk()

    def _files_from_staged(self) -> list[Path]:
        if not self.git_root:
            if not self._quiet:
                print("[QualityGate] Not a git repo; --staged requires git.")
            return []
        result = _git_cmd(self.git_root, ["diff", "--cached", "--name-only", "--diff-filter=ACM"])
        if result.returncode != 0:
            return []
        return self._filter_files([self.git_root / rel for rel in result.stdout.splitlines()])

    def _files_from_paths(self, paths: list[str]) -> list[Path]:
        out: list[Path] = []
        for raw in paths:
            p = Path(raw)
            if not p.is_absolute():
                candidate = (Path.cwd() / p).resolve()
                p = candidate if self._safe_exists(candidate) else (self.root_dir / p).resolve()
            if self._safe_is_file(p):
                out.append(p)
                continue
            if self._safe_is_dir(p):
                out.extend([child for child in p.rglob("*") if self._safe_is_file(child)])
        return self._filter_files(out, explicit=True)

    def _files_from_git_ls(self) -> list[Path]:
        if not self.git_root:
            return []
        result = _git_cmd(self.git_root, ["ls-files"])
        if result.returncode != 0:
            return []
        candidates = [
            (self.git_root / rel).resolve() for rel in result.stdout.splitlines() if rel.strip()
        ]
        return self._filter_files(candidates)

    def _files_from_walk(self) -> list[Path]:
        paths_cfg = (
            self.config.get("paths", {}) if isinstance(self.config.get("paths", {}), dict) else {}
        )
        includes = [str(p) for p in (paths_cfg.get("include", ["."]) or ["."])]
        out: list[Path] = []
        for inc in includes:
            path = (self.root_dir / inc).resolve()
            if not self._safe_exists(path):
                continue
            if self._safe_is_file(path):
                out.append(path)
            else:
                out.extend([p for p in path.rglob("*") if self._safe_is_file(p)])
        return self._filter_files(out)

    def _filter_files(self, candidates: list[Path], *, explicit: bool = False) -> list[Path]:
        files: list[Path] = []
        for p in candidates:
            if not self._safe_exists(p) or not self._safe_is_file(p):
                continue
            try:
                p.relative_to(self.root_dir)
            except ValueError:
                continue
            if not self._is_code_file(p):
                continue
            if not self._should_check_file(p, explicit=explicit):
                continue
            files.append(p)
        return files

    def check_file(self, file_path: Path) -> None:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            self._add_issue(
                file=file_path, line=0, rule="file_read_error", severity="error", message=f"{exc}"
            )
            return

        lines = content.splitlines()
        language = self._get_language(file_path)
        is_test = self._is_test_path(file_path)
        rel_file = self._rel_path(file_path)
        add_issue = self._mk_add_issue_for_file(file_path)

        self.stats["files_checked"] += 1
        self.stats["lines_checked"] += len(lines)

        self._run_builtin_checks(
            file_path=file_path,
            rel_file=rel_file,
            content=content,
            lines=lines,
            language=language,
            is_test=is_test,
            add_issue=add_issue,
        )
        self._run_modular_rules(
            file_path=file_path,
            content=content,
            lines=lines,
            language=language,
            is_test=is_test,
            add_issue=add_issue,
        )

    def _run_builtin_checks(
        self,
        *,
        file_path: Path,
        rel_file: str,
        content: str,
        lines: list[str],
        language: str,
        is_test: bool,
        add_issue: Callable[..., None],
    ) -> None:
        config = self.config
        check_file_size(
            rel_file=rel_file, file_path=file_path, lines=lines, config=config, add_issue=add_issue
        )
        self._run_builtin_content_checks(
            file_path=file_path,
            rel_file=rel_file,
            content=content,
            lines=lines,
            language=language,
            config=config,
            add_issue=add_issue,
        )
        self._run_builtin_test_checks(
            language=language,
            is_test=is_test,
            lines=lines,
            config=config,
            add_issue=add_issue,
        )
        self._run_builtin_import_checks(
            file_path=file_path,
            rel_file=rel_file,
            content=content,
            lines=lines,
            language=language,
            config=config,
            add_issue=add_issue,
        )

    def _run_builtin_content_checks(
        self,
        *,
        file_path: Path,
        rel_file: str,
        content: str,
        lines: list[str],
        language: str,
        config: dict[str, Any],
        add_issue: Callable[..., None],
    ) -> None:
        common = dict(
            file_path=file_path,
            content=content,
            language=language,
            config=config,
            add_issue=add_issue,
        )
        common_lines = dict(**common, lines=lines)
        check_function_size(rel_file=rel_file, **common_lines)
        check_no_todo_fixme(**common_lines)
        check_no_debug_statements(**common_lines)
        check_no_type_escape(**common_lines)
        check_no_silent_catch(**common)
        check_no_hardcoded_secrets(
            rel_file=rel_file, lines=lines, config=config, add_issue=add_issue
        )
        check_max_complexity(rel_file=rel_file, **common)

    def _run_builtin_test_checks(
        self,
        *,
        language: str,
        is_test: bool,
        lines: list[str],
        config: dict[str, Any],
        add_issue: Callable[..., None],
    ) -> None:
        test_common = dict(
            language=language,
            is_test=is_test,
            lines=lines,
            config=config,
            add_issue=add_issue,
        )
        check_noqa_ann001(**test_common)
        check_duplicate_class_defs(**test_common)
        check_classvar_in_tests(**test_common)
        check_test_parametrisation(**test_common)

    def _run_builtin_import_checks(
        self,
        *,
        file_path: Path,
        rel_file: str,
        content: str,
        lines: list[str],
        language: str,
        config: dict[str, Any],
        add_issue: Callable[..., None],
    ) -> None:
        check_import_count(language=language, lines=lines, config=config, add_issue=add_issue)
        check_import_boundaries(
            rel_file=rel_file,
            file_path=file_path,
            content=content,
            language=language,
            config=config,
            add_issue=add_issue,
        )

    def _run_modular_rules(
        self,
        *,
        file_path: Path,
        content: str,
        lines: list[str],
        language: str,
        is_test: bool,
        add_issue: Callable[..., None],
    ) -> None:
        ctx = RuleContext(
            file_path=file_path,
            content=content,
            lines=lines,
            language=language,
            is_test=is_test,
            config=self.config,
            add_issue=add_issue,
        )
        apply_phase1_rules(ctx)
        apply_phase2_rules(ctx)
        apply_ai_engineering_rules(ctx)
        apply_test_rules(ctx)

    def run(self, *, paths: list[str] | None, staged_only: bool, mode: str) -> CheckResult:
        files = self.get_files_to_check(paths, staged_only)
        if not files:
            if not self._quiet:
                print("[QualityGate] No files to check.")
            return CheckResult(passed=True, stats={"files_checked": 0})

        if not self._quiet:
            print(f"[QualityGate] Checking {len(files)} files...")

        all_files = self._load_all_files(files)
        apply_governance_rules(
            root_dir=self.root_dir, config=self.config, add_issue=self._add_issue
        )
        apply_eval_rules(root_dir=self.root_dir, config=self.config, add_issue=self._add_issue)
        for file_path in files:
            self.check_file(file_path)
        self._run_cross_file_checks(all_files)
        self._apply_prs(files)
        return self._final_result(mode=mode)

    def _load_all_files(self, files: list[Path]) -> dict[Path, tuple[str, list[str], str, bool]]:
        out: dict[Path, tuple[str, list[str], str, bool]] = {}
        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            lines = content.splitlines()
            out[file_path] = (
                content,
                lines,
                self._get_language(file_path),
                self._is_test_path(file_path),
            )
        return out

    def _run_cross_file_checks(
        self, all_files: dict[Path, tuple[str, list[str], str, bool]]
    ) -> None:
        check_duplicate_helpers(
            all_files=all_files,
            config=self.config,
            is_test_path=self._is_test_path,
            add_issue_for_path=self._mk_add_issue_for_file,
        )

    def _apply_prs(self, files: list[Path]) -> None:
        prs_cfg = self.config.get("prs", {}) if isinstance(self.config.get("prs", {}), dict) else {}
        if not bool(prs_cfg.get("enabled", True)):
            return

        min_score = int(prs_cfg.get("min_score", 85) or 85)
        error_weight = float(prs_cfg.get("error_weight", 10) or 10)
        warning_weight = float(prs_cfg.get("warning_weight", 2) or 2)

        counts: dict[str, dict[str, int]] = defaultdict(lambda: {"errors": 0, "warnings": 0})
        for issue in self.issues:
            if issue.rule == "prs_score":
                continue
            if issue.severity == Severity.ERROR:
                counts[issue.file]["errors"] += 1
            elif issue.severity == Severity.WARNING:
                counts[issue.file]["warnings"] += 1

        prs_failed = 0
        for file_path in files:
            rel = self._rel_path(file_path)
            c = counts.get(rel, {"errors": 0, "warnings": 0})
            score = 100.0 - (c["errors"] * error_weight) - (c["warnings"] * warning_weight)
            score = max(0.0, min(100.0, score))
            self.file_prs[rel] = {
                "score": round(float(score), 1),
                "min_score": int(min_score),
                "errors": int(c["errors"]),
                "warnings": int(c["warnings"]),
            }
            if score < float(min_score):
                prs_failed += 1
                self._add_issue(
                    file=rel,
                    line=1,
                    rule="prs_score",
                    severity="error",
                    message=f"PRS {score:.1f}/100 below minimum {min_score}.",
                    suggestion="Fix errors/warnings in this file; split large functions/files; remove debug/todos; improve error handling.",
                )

        self.stats["prs_files_scored"] = len(self.file_prs)
        self.stats["prs_files_failed"] = prs_failed
        self.stats["prs_min_score"] = int(min_score)

    def _final_result(self, *, mode: str) -> CheckResult:
        thresholds = (
            self.config.get("thresholds", {})
            if isinstance(self.config.get("thresholds", {}), dict)
            else {}
        )
        max_errors = int(thresholds.get("error_count", 0) or 0)
        max_warnings_raw = thresholds.get("warning_count", None)
        max_warnings = int(max_warnings_raw) if max_warnings_raw is not None else None

        passed = int(self.stats.get("error", 0)) <= max_errors
        if mode == "check" and max_warnings is not None:
            passed = passed and int(self.stats.get("warning", 0)) <= max_warnings
        return CheckResult(passed=passed, issues=self.issues, stats=dict(self.stats))

    def print_report(self, result: CheckResult, *, verbose: bool) -> None:
        print("\n" + "=" * 70)
        print("QUALITY GATE REPORT")
        print("=" * 70)
        self._print_summary(result)
        if not result.issues:
            print("\n[PASSED] No issues found.")
            return
        self._print_issues(result, verbose=verbose)
        print("\n" + "-" * 70)
        print("[FAILED]" if not result.passed else "[PASSED with warnings]")
        print("-" * 70)

    def _print_summary(self, result: CheckResult) -> None:
        print(f"\nFiles checked: {result.stats.get('files_checked', 0)}")
        print(f"Lines checked: {result.stats.get('lines_checked', 0)}")
        print(f"Errors: {result.stats.get('error', 0)}")
        print(f"Warnings: {result.stats.get('warning', 0)}")
        if "prs_files_scored" in result.stats:
            print(
                "PRS: "
                f"min={result.stats.get('prs_min_score')} "
                f"failed={result.stats.get('prs_files_failed')}/{result.stats.get('prs_files_scored')}"
            )

    def _print_issues(self, result: CheckResult, *, verbose: bool) -> None:
        print("\n" + "-" * 70)
        print("ISSUES BY FILE")
        print("-" * 70)
        by_file: dict[str, list[Issue]] = defaultdict(list)
        for issue in result.issues:
            by_file[issue.file].append(issue)
        for file, issues in sorted(by_file.items()):
            print(f"\n{file}:")
            for issue in sorted(issues, key=lambda x: x.line):
                if issue.severity == Severity.ERROR:
                    icon = "[E]"
                elif issue.severity == Severity.WARNING:
                    icon = "[W]"
                else:
                    icon = "[I]"
                print(f"  {icon} Line {issue.line}: [{issue.rule}] {issue.message}")
                if verbose and issue.code_snippet:
                    print(f"      > {issue.code_snippet}")
                if issue.suggestion and (verbose or issue.severity == Severity.ERROR):
                    print(f"      Fix: {issue.suggestion}")

    def generate_json_report(self, result: CheckResult) -> str:
        report = {
            "timestamp": datetime.now().isoformat(),
            "passed": result.passed,
            "stats": result.stats,
            "prs": self.file_prs,
            "issues": [
                {
                    "file": issue.file,
                    "line": issue.line,
                    "column": issue.column,
                    "rule": issue.rule,
                    "severity": issue.severity.value,
                    "message": issue.message,
                    "snippet": issue.code_snippet,
                    "suggestion": issue.suggestion,
                }
                for issue in result.issues
            ],
        }
        return json.dumps(report, indent=2)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Quality Gate - Portable Code Quality Enforcement",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("paths", nargs="*", help="Specific files or directories to check")
    parser.add_argument("--paths-from", help="Read newline-delimited paths from this file")
    parser.add_argument(
        "--staged", action="store_true", help="Check staged files only (for pre-commit)"
    )
    parser.add_argument(
        "--mode",
        choices=["check", "audit"],
        default="check",
        help="check=enforce, audit=report only",
    )
    parser.add_argument(
        "--top", type=int, default=0, help="In audit mode, print lowest PRS files (default: 0)"
    )
    parser.add_argument("--strict", action="store_true", help="Fail on warnings too")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--report", action="store_true", help="Generate detailed report files")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply safe deterministic fixes (best-effort; requires local tools like ruff/prettier).",
    )
    parser.add_argument(
        "--fix-all",
        action="store_true",
        help="Allow `--fix` to run on the entire repo (otherwise requires paths or --staged).",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print only the audit summary (still enforces in check mode).",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show code snippets and suggestions"
    )
    parser.add_argument(
        "--root", help="Project root directory (default: parent of this quality-gate folder)"
    )
    parser.add_argument("--no-prs", action="store_true", help="Disable PRS scoring/enforcement")
    parser.add_argument(
        "--min-score", type=int, default=None, help="Override PRS minimum score (default: 85)"
    )
    return parser.parse_args(argv)


def _read_paths_from_file(path: str) -> list[str]:
    p = Path(path)
    raw = p.read_text(encoding="utf-8", errors="ignore")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _print_audit_summary(result: CheckResult) -> None:
    print("QUALITY GATE AUDIT")
    print(f"Files checked: {result.stats.get('files_checked', 0)}")
    print(f"Errors: {result.stats.get('error', 0)}")
    print(f"Warnings: {result.stats.get('warning', 0)}")
    if "prs_files_scored" in result.stats:
        print(
            "PRS: "
            f"min={result.stats.get('prs_min_score')} "
            f"failed={result.stats.get('prs_files_failed')}/{result.stats.get('prs_files_scored')}"
        )


def _print_top_slop(gate: QualityGate, *, top: int) -> None:
    if top <= 0 or not gate.file_prs:
        return
    ranked = sorted(gate.file_prs.items(), key=lambda kv: float(kv[1].get("score", 0.0)))
    print("\nTop highest-slop files (lowest PRS):")
    for fp, meta in ranked[: min(int(top), len(ranked))]:
        print(
            f"  {meta.get('score')}/100  {fp}  (errors={meta.get('errors')}, warnings={meta.get('warnings')})"
        )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    gate = QualityGate(config_path=args.config, root_dir=args.root, quiet=bool(args.json))
    if args.no_prs:
        gate.config.setdefault("prs", {})["enabled"] = False
    if args.min_score is not None:
        gate.config.setdefault("prs", {})["min_score"] = int(args.min_score)

    paths: list[str] = list(args.paths or [])
    if args.paths_from:
        paths.extend(_read_paths_from_file(args.paths_from))

    if bool(getattr(args, "fix", False)):
        if not (paths or args.paths_from or args.staged or bool(getattr(args, "fix_all", False))):
            print("[QualityGate] Refusing to auto-fix the entire repo. Pass paths, `--staged`, or `--fix-all`.")
            return 2
        fix_files = gate.get_files_to_check(paths or None, staged_only=bool(args.staged))
        if fix_files:
            apply_deterministic_fixes(root_dir=gate.root_dir, files=fix_files, quiet=bool(args.json))
        elif not bool(args.json):
            print("[QualityGate] No files to fix.")

    result = gate.run(paths=paths or None, staged_only=bool(args.staged), mode=str(args.mode))
    if args.json:
        print(gate.generate_json_report(result))
    elif args.summary or (args.mode == "audit" and not args.verbose):
        _print_audit_summary(result)
    else:
        gate.print_report(result, verbose=bool(args.verbose))

    if args.mode == "audit":
        _print_top_slop(gate, top=int(args.top))
        if args.report:
            _write_report_file(gate, result)
        return 0

    if not result.passed:
        return 1
    if args.strict and int(result.stats.get("warning", 0)) > 0:
        return 2
    return 0


def _write_report_file(gate: QualityGate, result: CheckResult) -> None:
    os.makedirs(".quality-reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(".quality-reports") / f"report_{timestamp}.json"
    out_path.write_text(gate.generate_json_report(result), encoding="utf-8")
    print(f"\nReport saved to {out_path}")


if __name__ == "__main__":
    raise SystemExit(main())
