from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def apply_deterministic_fixes(*, root_dir: Path, files: list[Path], quiet: bool) -> None:
    py_files = [p for p in files if p.suffix.lower() == ".py"]
    web_files = [p for p in files if p.suffix.lower() in {".js", ".jsx", ".ts", ".tsx"}]

    def _print(msg: str) -> None:
        if not quiet:
            print(msg)

    if py_files:
        _run_ruff(root_dir=root_dir, py_files=py_files, quiet=quiet, print_fn=_print)
    if web_files:
        _run_prettier(root_dir=root_dir, web_files=web_files, quiet=quiet, print_fn=_print)


def _chunked_paths(paths: list[Path], *, chunk_size: int = 75) -> list[list[Path]]:
    if chunk_size <= 0:
        return [paths]
    return [paths[i : i + chunk_size] for i in range(0, len(paths), chunk_size)]


def _resolve_cmd(cmd: str, *, root_dir: Path) -> list[str] | None:
    found = shutil.which(cmd)
    if found:
        return [found]
    local_bin = root_dir / "node_modules" / ".bin"
    if os.name == "nt":
        candidates = [local_bin / f"{cmd}.cmd", local_bin / f"{cmd}.exe", local_bin / cmd]
    else:
        candidates = [local_bin / cmd]
    for candidate in candidates:
        if candidate.exists():
            return [str(candidate)]
    return None


def _run_optional_tool(*, label: str, argv: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        proc = subprocess.run(argv, cwd=str(cwd), check=False)
    except FileNotFoundError:
        return False, f"{label}: command not found"
    if proc.returncode != 0:
        return False, f"{label}: exited {proc.returncode}"
    return True, f"{label}: ok"


def _run_ruff(*, root_dir: Path, py_files: list[Path], quiet: bool, print_fn) -> None:
    ruff = _resolve_cmd("ruff", root_dir=root_dir)
    if not ruff:
        print_fn("[QualityGate] Skipped Python autofix: ruff not found.")
        return

    ok = True
    for chunk in _chunked_paths(py_files):
        chunk_ok, msg = _run_optional_tool(
            label="ruff format",
            argv=[*ruff, "format", *[str(p) for p in chunk]],
            cwd=root_dir,
        )
        ok = ok and chunk_ok
        if not chunk_ok and not quiet:
            print_fn(f"[QualityGate] {msg}")

    for chunk in _chunked_paths(py_files):
        chunk_ok, msg = _run_optional_tool(
            label="ruff check --fix",
            argv=[*ruff, "check", "--fix", *[str(p) for p in chunk]],
            cwd=root_dir,
        )
        ok = ok and chunk_ok
        if not chunk_ok and not quiet:
            print_fn(f"[QualityGate] {msg}")

    if ok:
        print_fn("[QualityGate] Applied Python fixes via ruff (format + safe autofix).")
    else:
        print_fn("[QualityGate] Python autofix attempted but some ruff steps failed.")


def _run_prettier(*, root_dir: Path, web_files: list[Path], quiet: bool, print_fn) -> None:
    prettier = _resolve_cmd("prettier", root_dir=root_dir)
    if not prettier:
        print_fn("[QualityGate] Skipped JS/TS autofix: prettier not found.")
        return

    ok = True
    for chunk in _chunked_paths(web_files):
        chunk_ok, msg = _run_optional_tool(
            label="prettier --write",
            argv=[*prettier, "--write", *[str(p) for p in chunk]],
            cwd=root_dir,
        )
        ok = ok and chunk_ok
        if not chunk_ok and not quiet:
            print_fn(f"[QualityGate] {msg}")

    if ok:
        print_fn("[QualityGate] Applied web fixes via prettier --write.")
    else:
        print_fn("[QualityGate] JS/TS autofix attempted but some prettier steps failed.")

