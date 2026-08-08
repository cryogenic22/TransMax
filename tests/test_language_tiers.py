"""TMX-LANG-TIERS / C-9 — the tier claim in `ProvenanceRecord.language_tier`
must be derived from the live pack registry + a PASSING eval run, never a
hardcoded table and never mere corpus-file existence (A3, seam invariant C-9).

The original module shipped a defect (caught in the 2026-08-08 review): it
awarded QUALIFIED whenever a golden corpus *file* existed, so dropping one
unevaluated JSON case on disk lifted a language to the strongest tier without
anything being measured. These tests pin the honest contract: QUALIFIED
requires a persisted eval report in which the pair actually ran and passed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

from app.core.language_tiers import LanguageTier, resolve_language_tier
from app.services.language_packs.base import BaseLanguagePack
from app.services.language_packs.factory import GenericLanguagePack, LanguagePackFactory


def _write_report(tmp_path: Path, pairs: List[Tuple[str, int, int]]) -> Path:
    """Write an eval report (tests/evals/runner.py schema). `pairs` is a list
    of (language_pair, total, failed)."""
    suites = [
        {
            "suite": f"data/{pair.replace('-', '_')}/critical_safety.jsonl",
            "language_pair": pair,
            "total": total,
            "passed": total - failed,
            "failed": failed,
            "failures": [],
        }
        for (pair, total, failed) in pairs
    ]
    report = {
        "scope": "harness-only",
        "suites": suites,
        "total": sum(t for _, t, _ in pairs),
        "passed": sum(t - f for _, t, f in pairs),
        "failed": sum(f for _, _, f in pairs),
        "skipped": 0,
        "failures": [],
    }
    path = tmp_path / "latest.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


# ── The honesty fix: corpus existence alone must NOT qualify ─────────────────


def test_deep_pack_without_a_passing_run_is_supported_not_qualified():
    # "es" has a deep SpanishPack AND a real en_es corpus on disk, but no
    # committed eval report proves a passing run -> SUPPORTED, never QUALIFIED.
    # This is the exact defect the review caught: existence != measured.
    assert resolve_language_tier("es") == LanguageTier.SUPPORTED


def test_passing_eval_record_earns_qualified(tmp_path: Path):
    report = _write_report(tmp_path, [("en-es", 5, 0)])
    assert (
        resolve_language_tier("es", eval_report_path=report) == LanguageTier.QUALIFIED
    )


def test_a_recorded_FAILING_run_does_not_qualify(tmp_path: Path):
    # A run that executed but had failures is NOT a qualification — this is the
    # sharpest honesty case: measured-and-failing must never read as measured-
    # and-passing.
    report = _write_report(tmp_path, [("en-es", 5, 2)])
    assert (
        resolve_language_tier("es", eval_report_path=report) == LanguageTier.SUPPORTED
    )


def test_an_empty_suite_does_not_qualify(tmp_path: Path):
    # total == 0 means nothing was actually evaluated.
    report = _write_report(tmp_path, [("en-es", 0, 0)])
    assert (
        resolve_language_tier("es", eval_report_path=report) == LanguageTier.SUPPORTED
    )


def test_pair_absent_from_report_does_not_qualify(tmp_path: Path):
    # A passing record for a DIFFERENT pair must not qualify es.
    report = _write_report(tmp_path, [("en-de", 5, 0)])
    assert (
        resolve_language_tier("es", eval_report_path=report) == LanguageTier.SUPPORTED
    )


def test_missing_report_file_does_not_qualify(tmp_path: Path):
    assert (
        resolve_language_tier("es", eval_report_path=tmp_path / "nope.json")
        == LanguageTier.SUPPORTED
    )


# ── AVAILABLE: no deep pack at all ──────────────────────────────────────────


def test_no_pack_resolves_available():
    # Swahili has no dedicated pack and no BCP-47 fallback -> generic only.
    pack = LanguagePackFactory.get_pack("sw")
    assert isinstance(pack, GenericLanguagePack)
    assert resolve_language_tier("sw") == LanguageTier.AVAILABLE


# ── Derivation, not a hardcoded table ───────────────────────────────────────


def test_tier_is_derived_not_hardcoded_via_pack_registry_monkeypatch(monkeypatch):
    # Before: "xx" has no pack registered -> AVAILABLE.
    assert "xx" not in LanguagePackFactory._packs
    assert resolve_language_tier("xx") == LanguageTier.AVAILABLE

    # Register a fake deep (non-Generic) pack for "xx" directly on the live
    # registry and prove the result flips to SUPPORTED purely because the
    # registry changed underneath it (no passing run -> not QUALIFIED).
    class _FakeDeepPack(BaseLanguagePack):
        @property
        def code(self) -> str:
            return "xx"

        @property
        def script_direction(self) -> str:
            return "ltr"

    fake_packs = dict(LanguagePackFactory._packs)
    fake_packs["xx"] = _FakeDeepPack()
    monkeypatch.setattr(LanguagePackFactory, "_packs", fake_packs)

    assert resolve_language_tier("xx") == LanguageTier.SUPPORTED


def test_tier_flips_with_the_eval_report_fixture(tmp_path: Path):
    # "es" is a real deep pack. With no passing record -> SUPPORTED; point the
    # lookup at a report that records en-es passing and it flips to QUALIFIED —
    # driven entirely by the report artefact, not any table inside the module.
    assert resolve_language_tier("es") == LanguageTier.SUPPORTED

    report = _write_report(tmp_path, [("en-es", 3, 0)])
    assert (
        resolve_language_tier("es", eval_report_path=report) == LanguageTier.QUALIFIED
    )


def test_unknown_garbage_code_resolves_available_never_raises():
    assert resolve_language_tier("this-is-not-a-real-language-xyz123") == LanguageTier.AVAILABLE
    assert resolve_language_tier("") == LanguageTier.AVAILABLE
    assert resolve_language_tier("   ") == LanguageTier.AVAILABLE
