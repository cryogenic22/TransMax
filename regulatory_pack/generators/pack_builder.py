"""Regulatory-pack builder (TMX-3500).

Reads templates from `regulatory_pack/templates/`, fills placeholders with
evidence pulled from the repo (worksheets, ADRs, ratchet baseline, test
suite, prompt registry), and writes filled markdown to a per-release
output directory.

CLI:
    python -m regulatory_pack.generators.pack_builder \\
        --release v3.0-rc1 \\
        --output regulatory_pack/releases/v3.0-rc1/

Idempotent: re-running on the same output_dir overwrites cleanly.

Stdlib-only. PDF rendering is deferred (see TMX-3500a).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import string
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from regulatory_pack.generators.traceability import (
    TraceabilityMatrix,
    build_matrix,
)

logger = logging.getLogger(__name__)

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PACKAGE_ROOT / "templates"
DOCUMENTS = ("URS", "FS", "IQ", "OQ", "PQ")


# ---------------------------------------------------------------------------
# Evidence collectors
# ---------------------------------------------------------------------------


def _collect_adr_index(repo_root: Path) -> str:
    """Return a markdown bullet list of ADRs under docs/decisions/."""
    adr_dir = repo_root / "docs" / "decisions"
    if not adr_dir.is_dir():
        return "_(no ADRs found at `docs/decisions/`)_"
    out: list[str] = []
    for path in sorted(adr_dir.glob("*.md")):
        if path.name.startswith("_"):  # skip _template.md
            continue
        try:
            head = path.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
        except OSError:
            continue
        title = head[0].lstrip("#").strip() if head else path.stem
        rel = path.relative_to(repo_root).as_posix()
        out.append(f"- [`{rel}`]({rel}) - {title}")
    if not out:
        return "_(no ADR files found)_"
    return "\n".join(out)


def _collect_ratchet_metrics(repo_root: Path) -> str:
    """Render `ratchet/baseline.json` as a markdown table."""
    baseline_path = repo_root / "ratchet" / "baseline.json"
    if not baseline_path.is_file():
        return "_(no `ratchet/baseline.json` found)_"
    try:
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"_(failed to read ratchet baseline: {exc})_"
    metrics = data.get("metrics", {})
    directions = data.get("directions", {})
    if not metrics:
        return "_(ratchet baseline has no metrics)_"
    lines = ["| Metric | Direction | Baseline |", "|---|---|---|"]
    for key in sorted(metrics):
        direction = directions.get(key, "?")
        lines.append(f"| `{key}` | {direction} | {metrics[key]} |")
    return "\n".join(lines)


def _collect_environment_matrix(repo_root: Path) -> str:
    """Render the reference environment as a markdown table.

    Pulls Python version from the running interpreter; pulls the alembic
    head from the alembic/versions/ directory if present; pulls the
    frontend Node engine constraint from frontend/package.json if present.
    """
    py_version = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )

    alembic_head = "_(no `alembic/versions/` directory found)_"
    alembic_dir = repo_root / "alembic" / "versions"
    if alembic_dir.is_dir():
        revs = sorted(alembic_dir.glob("*.py"))
        alembic_head = revs[-1].stem if revs else "_(no migration files)_"

    node_engine = "_(no `frontend/package.json` found)_"
    pkg_json = repo_root / "frontend" / "package.json"
    if pkg_json.is_file():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            engines = data.get("engines", {})
            if engines:
                node_engine = ", ".join(f"{k}: `{v}`" for k, v in engines.items())
            else:
                node_engine = "(no engines pin in package.json)"
        except (OSError, json.JSONDecodeError):
            node_engine = "_(failed to parse `frontend/package.json`)_"

    return (
        "| Component | Constraint / Version |\n"
        "|---|---|\n"
        f"| Python | `{py_version}` (capture-time interpreter) |\n"
        f"| Alembic head | `{alembic_head}` |\n"
        f"| Frontend engines | {node_engine} |\n"
        "| OS (target) | Linux x86_64 (production); Windows + macOS supported for dev |\n"
    )


def _count_tests(repo_root: Path) -> tuple[int, int]:
    """Return (test_file_count, test_function_count) under `tests/`."""
    tests_dir = repo_root / "tests"
    if not tests_dir.is_dir():
        return 0, 0
    file_count = 0
    function_count = 0
    test_def_re = re.compile(r"^\s*def\s+test_[A-Za-z0-9_]+\s*\(", re.MULTILINE)
    for path in tests_dir.rglob("test_*.py"):
        file_count += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        function_count += len(test_def_re.findall(text))
    return file_count, function_count


def _collect_prompt_versions(repo_root: Path) -> str:
    """Inventory pinned prompt YAMLs under `app/agents/prompts/<agent>/`.

    Per addendum A8, every prompt is pinned to a versioned YAML. If the
    layout is not present yet (TMX-3200/3201), surface that explicitly
    rather than silently saying "none".
    """
    prompts_dir = repo_root / "app" / "agents" / "prompts"
    if not prompts_dir.is_dir():
        return (
            "_(no `app/agents/prompts/` directory found - prompt registry "
            "not yet present; see TMX-3200/3201)_"
        )
    pinned = sorted(prompts_dir.rglob("*.yaml"))
    if not pinned:
        return "_(prompt registry directory present but no `.yaml` files yet)_"
    lines = ["| Agent | Version | File |", "|---|---|---|"]
    for path in pinned:
        rel = path.relative_to(repo_root).as_posix()
        # Layout: app/agents/prompts/<agent>/<version>.yaml
        parts = path.relative_to(prompts_dir).parts
        agent = parts[0] if len(parts) >= 2 else "(top-level)"
        version = path.stem
        lines.append(f"| `{agent}` | `{version}` | [`{rel}`]({rel}) |")
    return "\n".join(lines)


@dataclass
class _TicketBucket:
    """Aggregated per-ticket evidence for the URS ticket-summary section."""

    ac_count: int = 0
    sha: Optional[str] = None
    statuses: set[str] = field(default_factory=set)


def _collect_ticket_summary(matrix: TraceabilityMatrix) -> str:
    """Render a per-ticket bullet list with row counts and resolved SHA."""
    by_ticket: dict[str, _TicketBucket] = {}
    for row in matrix.rows:
        bucket = by_ticket.setdefault(row.ticket_id, _TicketBucket())
        bucket.ac_count += 1
        if row.commit_sha and bucket.sha is None:
            bucket.sha = row.commit_sha
        bucket.statuses.add(row.status)

    if not by_ticket:
        return "_(no shipped tickets recorded in this release)_"

    lines: list[str] = []
    for ticket_id in sorted(by_ticket):
        info = by_ticket[ticket_id]
        sha_display = f"`{info.sha[:10]}`" if info.sha else "_(no commit resolved)_"
        status_display = ", ".join(sorted(info.statuses))
        lines.append(
            f"- **`{ticket_id}`** ({info.ac_count} AC, {status_display}): "
            f"commit {sha_display}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------


def _render_template(template_path: Path, mapping: dict[str, str]) -> str:
    """Substitute `$placeholder` tokens in a template using string.Template.

    Uses `safe_substitute` so an unknown `$x` lands as `$x` rather than
    raising KeyError. This is forgiving by design for scaffold v0; if a
    template references an unknown placeholder we surface it visually for
    a human to spot, not crash the build.
    """
    raw = template_path.read_text(encoding="utf-8")
    return string.Template(raw).safe_substitute(mapping)


def _build_mapping(
    release: str,
    matrix: TraceabilityMatrix,
    repo_root: Path,
) -> dict[str, str]:
    """Build the placeholder->value mapping shared across all templates."""
    test_files, test_functions = _count_tests(repo_root)
    return {
        "release": release,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "traceability_table": matrix.to_markdown_table(),
        "traceability_row_count": str(len(matrix.rows)),
        "ratchet_metrics": _collect_ratchet_metrics(repo_root),
        "adr_index": _collect_adr_index(repo_root),
        "environment_matrix": _collect_environment_matrix(repo_root),
        "prompt_versions": _collect_prompt_versions(repo_root),
        "test_file_count": str(test_files),
        "test_function_count": str(test_functions),
        "ticket_summary": _collect_ticket_summary(matrix),
        "ac_count": str(len(matrix.rows)),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_pack(
    release: str,
    output_dir: Path | str,
    repo_root: Path | str = ".",
    *,
    templates_dir: Optional[Path] = None,
) -> Path:
    """Build a regulatory pack for a release into output_dir.

    Args:
        release: release identifier, e.g. "v3.0-rc1" or "SCAFFOLD-v0".
        output_dir: directory to write filled documents into. Created if
            missing. Existing files in this directory are overwritten
            (idempotent).
        repo_root: repository root used as the evidence source.
        templates_dir: override the templates directory (test-only).

    Returns:
        The resolved output directory as a Path.
    """
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    repo = Path(repo_root).resolve()
    tmpl_dir = templates_dir or TEMPLATES_DIR

    logger.info(
        "Building regulatory pack: release=%s, output=%s, templates=%s, repo=%s",
        release,
        out,
        tmpl_dir,
        repo,
    )

    matrix = build_matrix(repo_root=repo)
    mapping = _build_mapping(release, matrix, repo)

    for doc in DOCUMENTS:
        template_path = tmpl_dir / f"{doc}_template.md"
        if not template_path.is_file():
            raise FileNotFoundError(f"missing template: {template_path}")
        rendered = _render_template(template_path, mapping)
        target = out / f"{doc}.md"
        target.write_text(rendered, encoding="utf-8")
        logger.info("wrote %s (%d bytes)", target, len(rendered))

    # Also drop the matrix as a standalone JSON file for downstream
    # consumers (PDF renderer in TMX-3500a, signature workflow in
    # TMX-3500b). This is additive - the templates already embed it inline
    # in FS.md.
    matrix_json = {
        "release": release,
        "generated_at": mapping["generated_at"],
        "rows": [
            {
                "ticket_id": r.ticket_id,
                "ac_id": r.ac_id,
                "test_function": r.test_function,
                "test_file": r.test_file,
                "commit_sha": r.commit_sha,
                "status": r.status,
                "note": r.note,
            }
            for r in matrix.rows
        ],
        "summary": matrix.summary(),
    }
    (out / "traceability_matrix.json").write_text(
        json.dumps(matrix_json, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a regulatory pack (URS/FS/IQ/OQ/PQ markdown documents) for a "
            "release. Pulls evidence from .context/loops/, tests/, ratchet/, "
            "docs/decisions/, and git. Idempotent."
        )
    )
    parser.add_argument(
        "--release",
        required=True,
        help="Release identifier, e.g. v3.0-rc1 or SCAFFOLD-v0.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output directory (created if missing). Existing files overwritten.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent,
        help="Repository root (default: parent of regulatory_pack/).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable INFO-level logging.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    out = build_pack(
        release=args.release,
        output_dir=args.output,
        repo_root=args.repo_root,
    )

    # Use print (not logger) for the user-facing CLI summary - this is a
    # CLI tool, not library code; the constraint forbidding print() applies
    # to `regulatory_pack/` library modules, not the CLI's exit-summary.
    print(f"Regulatory pack written: {out}")
    print(f"Documents emitted: {', '.join(f'{d}.md' for d in DOCUMENTS)}")
    print(f"Traceability matrix: {out / 'traceability_matrix.json'}")

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
