"""TMX-LANG-TIERS — declared language support tiers (seam invariant C-9).

`ProvenanceRecord.language_tier` (`app/schemas/api_v1.py`, ADR-0009 clause 3/5)
exists but has never been populated with a real value — it always defaults to
``None``. This module makes the field honest by deriving a three-tier claim
from the two artefacts that can actually earn it, at call time:

1. **Deep pack** — does `LanguagePackFactory` resolve `lang_code` to a
   language-specific pack (e.g. `SpanishPack`), or does it fall through to
   `GenericLanguagePack` (universal gates only, no language-specific
   rigor)? Read from the live registry in `app/services/language_packs/factory.py`.
2. **Golden eval coverage** — does a golden critical-safety corpus exist for
   the (source, target) pair under `tests/evals/data/<source>_<target>/`?
   Read from the filesystem, not from `tests/evals/runner.py`'s `SUITES`
   list — that list is a hand-maintained CI-registration table (currently
   incomplete relative to the data directories that exist) and is exactly
   the kind of stored assertion this module must not depend on.

Both facts are re-read on every call. No language->tier table is stored
anywhere (A3 / ADR-0009 clause 5): a language that today has only the
generic fallback pack must never be indistinguishable, in provenance, from
one with a deep pack and a measured corpus.
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
_EVAL_DATA_ROOT = _REPO_ROOT / "tests" / "evals" / "data"
_GOLDEN_CORPUS_FILENAME = "critical_safety.jsonl"


class LanguageTier(str, Enum):
    """A support-tier claim the engine can defend, per C-9.

    QUALIFIED — a deep language pack exists AND golden eval cases cover the
        pair: the strongest claim, backed by both a specialised gate set and
        a measured critical-defect recall corpus.
    SUPPORTED — a deep language pack exists but the pair has no golden eval
        corpus: specialised gates run, but recall is unmeasured.
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


def _has_golden_eval_coverage(
    source_lang: str, target_lang: str, eval_data_root: Path
) -> bool:
    """True iff a non-empty golden critical-safety corpus exists on disk for
    this (source, target) pair. A present-but-empty or unparseable file does
    not count as coverage — an empty file proves nothing was measured.
    """
    corpus_path = (
        eval_data_root / f"{source_lang.lower()}_{target_lang.lower()}" / _GOLDEN_CORPUS_FILENAME
    )
    if not corpus_path.is_file():
        return False
    try:
        with corpus_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                json.loads(line)  # a real case, not just a present file
                return True
    except (OSError, json.JSONDecodeError):
        return False
    return False


def resolve_language_tier(
    lang_code: str,
    pair: Optional[Tuple[str, str]] = None,
    *,
    eval_data_root: Optional[Path] = None,
) -> LanguageTier:
    """Derive the support tier for `lang_code` from the live pack registry
    and the on-disk golden eval corpus — never from a hardcoded table.

    `pair` is the explicit `(source_lang, target_lang)` this claim is about;
    it defaults to `(DEFAULT_SOURCE_LANG, lang_code)` since every shipped
    corpus today is English-sourced and `ProvenanceRecord` carries a single
    target-facing field. `eval_data_root` overrides the corpus search root
    (tests use this to prove the result is derived, not memorised).

    Never raises: an unknown, malformed, or empty code resolves to
    AVAILABLE rather than crashing or defaulting to a claim it hasn't
    earned.
    """
    if not lang_code or not lang_code.strip():
        return LanguageTier.AVAILABLE

    if not _has_deep_pack(lang_code):
        return LanguageTier.AVAILABLE

    source_lang, target_lang = pair if pair is not None else (DEFAULT_SOURCE_LANG, lang_code)
    root = eval_data_root if eval_data_root is not None else _EVAL_DATA_ROOT
    if _has_golden_eval_coverage(source_lang, target_lang, root):
        return LanguageTier.QUALIFIED

    return LanguageTier.SUPPORTED
