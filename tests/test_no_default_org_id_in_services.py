"""TMX-3012d — regression test: DEFAULT_ORG_ID only appears in four canonical files.

The 2026-05-09 audit §4.1 / §6 flagged residual transitional markers across the
service layer after TMX-3012c. This test makes the cosmetic close into a
permanent invariant: any future re-introduction of `DEFAULT_ORG_ID` outside the
canonical four files fails CI.

Why these four are canonical (per CLAUDE.md and the TMX-3012/3012b/3012c loops):

- ``app/models/database.py`` — the constant DEFINITION + Organization docstring.
- ``app/main.py`` — ``TenantContextMiddleware`` request-boundary fallback.
- ``app/core/database.py`` — ``_seed_default_org()`` startup helper (no request
  context exists at boot, so the literal is the correct seed value).
- ``app/models/tenant_scoped.py`` — docstring describing the precedence the
  ``_inject_org_id`` listener uses.

Anything else is a transitional marker that should have been removed when
TMX-3012/3012b/3012c shipped. The mixin's ``before_insert`` listener already
raises ``TenantContextMissing`` if no context is set (per A3 — no silent
fallbacks), so the literal is redundant; keeping it MASKS a context-propagation
defect rather than fixing one.
"""
from __future__ import annotations

from pathlib import Path

# Resolve the repo's ``app/`` directory from this test file's location so the
# test is independent of the pytest cwd.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_APP_DIR = _REPO_ROOT / "app"

CANONICAL_FILES = frozenset(
    {
        _APP_DIR / "models" / "database.py",
        _APP_DIR / "main.py",
        _APP_DIR / "core" / "database.py",
        _APP_DIR / "models" / "tenant_scoped.py",
    }
)

NEEDLE = "DEFAULT_ORG_ID"


def test_default_org_id_only_in_canonical_locations() -> None:
    """``DEFAULT_ORG_ID`` may only appear in the four canonical files."""
    violators: list[str] = []

    for py_file in sorted(_APP_DIR.rglob("*.py")):
        if py_file in CANONICAL_FILES:
            continue
        try:
            text = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if NEEDLE in line:
                rel = py_file.relative_to(_REPO_ROOT).as_posix()
                violators.append(f"  {rel}:{lineno}  {line.strip()}")

    assert not violators, (
        "DEFAULT_ORG_ID appears outside canonical files (TMX-3012d):\n"
        + "\n".join(violators)
        + "\n\nIf you truly need to reference DEFAULT_ORG_ID outside "
        + "models/database.py, main.py, core/database.py, or models/tenant_scoped.py, "
        + "the right fix is almost certainly to wrap the work in `org_context(...)` "
        + "and let the TenantScopedMixin listener inject organization_id. "
        + "See CLAUDE.md addendum A3."
    )
