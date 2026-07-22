"""TMX-LANG-TIERS — the tier claim in `ProvenanceRecord.language_tier` must be
derived from the live pack registry + golden eval corpus, never a hardcoded
language->tier table (seam invariant C-9, A3).

Five cases, matching the ticket's red-test list:
  (a) deep pack + golden eval corpus  -> QUALIFIED (en->es, real corpus)
  (b) deep pack, no golden eval corpus -> SUPPORTED (en->fr, real corpus absent)
  (c) no pack at all                   -> AVAILABLE (a real unregistered code)
  (d) the tier is DERIVED, not looked up in a table: monkeypatching the pack
      registry and pointing the eval-corpus lookup at a fixture both flip
      the result, proving there is no shortcut hardcoded table underneath.
  (e) unknown/garbage code              -> AVAILABLE, never raises.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.core.language_tiers import LanguageTier, resolve_language_tier
from app.services.language_packs.base import BaseLanguagePack
from app.services.language_packs.factory import GenericLanguagePack, LanguagePackFactory


def test_deep_pack_with_golden_eval_corpus_resolves_qualified():
    # en->es: SpanishPack is a deep pack, and tests/evals/data/en_es/
    # carries a real critical-safety corpus.
    assert resolve_language_tier("es") == LanguageTier.QUALIFIED


def test_deep_pack_without_golden_eval_corpus_resolves_supported():
    # en->fr: FrenchPack is a deep pack, but no tests/evals/data/en_fr/
    # directory exists yet — no coverage claim can be made.
    assert not (Path("tests/evals/data/en_fr")).exists()
    assert resolve_language_tier("fr") == LanguageTier.SUPPORTED


def test_no_pack_resolves_available():
    # Swahili has no dedicated pack and no BCP-47 fallback -> generic only.
    pack = LanguagePackFactory.get_pack("sw")
    assert isinstance(pack, GenericLanguagePack)
    assert resolve_language_tier("sw") == LanguageTier.AVAILABLE


def test_tier_is_derived_not_hardcoded_via_pack_registry_monkeypatch(monkeypatch):
    # Before: "xx" has no pack registered -> AVAILABLE.
    assert "xx" not in LanguagePackFactory._packs
    assert resolve_language_tier("xx") == LanguageTier.AVAILABLE

    # Register a fake deep (non-Generic) pack for "xx" directly on the live
    # registry (not through this module) and prove the result flips to
    # SUPPORTED purely because the registry changed underneath it.
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


def test_tier_is_derived_not_hardcoded_via_eval_corpus_fixture(tmp_path: Path):
    # "fr" is a real deep pack with no shipped corpus -> SUPPORTED by
    # default. Point the eval-corpus lookup at a fixture directory that DOES
    # carry a corpus for en_fr and prove the result flips to QUALIFIED —
    # driven entirely by the fixture, not by any table inside the module.
    assert resolve_language_tier("fr") == LanguageTier.SUPPORTED

    fixture_root = tmp_path / "eval_data"
    corpus_dir = fixture_root / "en_fr"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "critical_safety.jsonl").write_text(
        json.dumps({"id": "fixture-1", "kind": "tampered", "source": "x", "target": "y"}) + "\n",
        encoding="utf-8",
    )

    assert (
        resolve_language_tier("fr", eval_data_root=fixture_root)
        == LanguageTier.QUALIFIED
    )


def test_unknown_garbage_code_resolves_available_never_raises():
    assert resolve_language_tier("this-is-not-a-real-language-xyz123") == LanguageTier.AVAILABLE
    assert resolve_language_tier("") == LanguageTier.AVAILABLE
    assert resolve_language_tier("   ") == LanguageTier.AVAILABLE
