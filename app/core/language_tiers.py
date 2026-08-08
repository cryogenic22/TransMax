"""TMX-LANG-TIERS — declared language support tiers (seam invariant C-9).

`ProvenanceRecord.language_tier` (`app/schemas/api_v1.py`, ADR-0009 clause 3/5)
exists but has never been populated with a real value — it always defaults to
``None``. This module makes the field honest by deriving a three-tier claim
from the artefacts that can actually *earn* it, at call time:

1. **Deep pack** — does `LanguagePackFactory` resolve `lang_code` to a
   language-specific pack (e.g. `SpanishPack`), or does it fall through to
   `GenericLanguagePack` (universal gates only, no language-specific rigor)?
   Read from the live registry in `app/services/language_packs/factory.py`.
2. **A passing measured eval run** — is there a persisted eval report
   (`tests/evals/runner.py`'s JSON output) in which this (source, target)
   pair's suite actually ran (``total > 0``) and passed with zero failures
   (``failed == 0``)? The mere *existence* of a golden corpus file proves
   nothing: an unevaluated case someone dropped on disk must NOT lift a
   language to the strongest tier. That was the original defect this module
   shipped with (QUALIFIED was awarded on corpus-file existence) and it is
   exactly the unearned-claim class C-9/A3 forbid — only a recorded passing
   run earns QUALIFIED.

Both facts are re-derived on every call; no language->tier table is stored
anywhere (A3 / ADR-0009 clause 5).

NOTE (scope): this function has no live consumer in ``app/`` yet — wiring into
`ProvenanceRecord` is deferred (it is constructed nowhere today, so forcing a
call site would be fake wiring). When it IS wired, QUALIFIED should also weigh
report freshness / eval-harness version / reviewer sign-off; those artefacts
do not exist to read today, so gating on them now would be inventing evidence
rather than reading it. The passing-run record is the honest floor.
"""
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple

from app.services.language_packs.factory import GenericLanguagePack, LanguagePackFactory

# TransMax's evals are keyed by (source, target); every shipped corpus today
# is sourced from English, so this is the default source when the caller
# only has a target code (matches ProvenanceRecord's single-language field).
DEFAULT_SOURCE_LANG = "en"

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# The eval runner's documented output path (see tests/evals/runner.py usage).
_DEFAULT_EVAL_REPORT = _REPO_ROOT / "eval_results" / "latest.json"


class LanguageTier(str, Enum):
    """A support-tier claim the engine can defend, per C-9.

    QUALIFIED — a deep language pack exists AND a persisted eval run records
        this pair passing (>=1 case evaluated, zero failures): the strongest
        claim, backed by a specialised gate set and a *measured* critical-
        defect run.
    SUPPORTED — a deep language pack exists but no passing eval run is on
        record for the pair: specialised gates run, but recall is unproven.
    AVAILABLE — the generic fallback pack only. No quality claim may be made
        beyond "the universal gates ran".
    """

    QUALIFIED = "QUALIFIED"
    SUPPORTED = "SUPPORTED"
    AVAILABLE = "AVAILABLE"


def _has_deep_pack(lang_code: str) -> bool:
    """True iff the registry resolves `lang_code` to a language-specific
    pack rather than the generic fallback. Reads the live registry — never
    a duplicated list of "which languages are deep".
    """
    pack = LanguagePackFactory.get_pack(lang_code)
    return not isinstance(pack, GenericLanguagePack)


def _has_passing_eval_record(
    source_lang: str, target_lang: str, report_path: Path
) -> bool:
    """True iff a persisted eval report shows this (source, target) pair's
    suite actually ran and passed.

    "Passed" means the runner recorded the pair with ``total > 0`` (cases were
    evaluated) and ``failed == 0`` (none regressed). A missing report, a pair
    absent from it, an empty suite, or any parse error all mean "not proven"
    -> False. Corpus files on disk are deliberately NOT consulted: their
    presence is not evidence that anything was measured.
    """
    if not report_path.is_file():
        return False
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(report, dict):
        return False
    pair = f"{source_lang.lower()}-{target_lang.lower()}"
    for suite in report.get("suites", []):
        if not isinstance(suite, dict):
            continue
        if str(suite.get("language_pair", "")).lower() != pair:
            continue
        total = suite.get("total")
        failed = suite.get("failed")
        if isinstance(total, int) and isinstance(failed, int) and total > 0 and failed == 0:
            return True
    return False


def resolve_language_tier(
    lang_code: str,
    pair: Optional[Tuple[str, str]] = None,
    *,
    eval_report_path: Optional[Path] = None,
) -> LanguageTier:
    """Derive the support tier for `lang_code` from the live pack registry and
    a persisted passing eval run — never from a hardcoded table or from mere
    test-data existence.

    `pair` is the explicit `(source_lang, target_lang)` this claim is about;
    it defaults to `(DEFAULT_SOURCE_LANG, lang_code)` since every shipped
    corpus today is English-sourced and `ProvenanceRecord` carries a single
    target-facing field. `eval_report_path` overrides the eval-report location
    (tests use this to prove the result is derived from a recorded pass).

    Never raises: an unknown, malformed, or empty code — or a missing report —
    resolves downward (AVAILABLE / SUPPORTED) rather than to a claim it hasn't
    earned.
    """
    if not lang_code or not lang_code.strip():
        return LanguageTier.AVAILABLE

    if not _has_deep_pack(lang_code):
        return LanguageTier.AVAILABLE

    source_lang, target_lang = pair if pair is not None else (DEFAULT_SOURCE_LANG, lang_code)
    report_path = eval_report_path if eval_report_path is not None else _DEFAULT_EVAL_REPORT
    if _has_passing_eval_record(source_lang, target_lang, report_path):
        return LanguageTier.QUALIFIED

    return LanguageTier.SUPPORTED
