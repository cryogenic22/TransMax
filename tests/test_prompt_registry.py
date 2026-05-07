"""
TMX-3200 + TMX-3201 — PromptRegistry contract tests.

Per addendum A8 (pin every prompt to a version): all prompts live in
app/agents/prompts/<agent>/v<X.Y.Z>.yaml. The registry must:
  - Resolve `latest` to the highest semver on disk
  - Cache loads (one read per (agent, version) per process)
  - Compute a stable content_hash so JobConfigSnapshot can record it
  - Reject malformed YAML / schema violations loudly
  - Migrate the legacy TransMaxPrompts constants byte-equivalent (modulo
    YAML literal-block leading-newline behaviour)
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.agents.prompts import (
    PromptNotFoundError,
    PromptRegistry,
    PromptSchemaError,
    PromptVersion,
)


# ── Basic load semantics ────────────────────────────────────────────────


def test_registry_loads_translator_v1_0_0() -> None:
    p = PromptRegistry.load("translator", "1.0.0")
    assert isinstance(p, PromptVersion)
    assert p.agent == "translator"
    assert p.version == "1.0.0"
    assert "TransMax Translator" in p.system
    assert "{{target_language}}" in p.user


def test_registry_latest_resolves_to_v1_0_0_for_translator() -> None:
    latest = PromptRegistry.load("translator")
    explicit = PromptRegistry.load("translator", "1.0.0")
    assert latest.version == explicit.version
    assert latest.content_hash == explicit.content_hash


def test_registry_loads_fixer() -> None:
    p = PromptRegistry.load("fixer")
    assert "Targeted Fixer" in p.system
    assert "{{segments_to_fix_json}}" in p.user


def test_registry_loads_reviewer() -> None:
    # Reviewer is migrated even though no live caller wires it (TMX-3201
    # spec — pin every prompt for A8 compliance).
    p = PromptRegistry.load("reviewer")
    assert "Semantic Reviewer" in p.system
    assert "{{source_language}}" in p.user


# ── content_hash semantics ──────────────────────────────────────────────


def test_content_hash_is_stable_across_reads() -> None:
    h1 = PromptRegistry.load("translator").content_hash
    h2 = PromptRegistry.load("translator").content_hash
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex length


def test_content_hash_matches_explicit_sha256() -> None:
    p = PromptRegistry.load("translator")
    expected = hashlib.sha256(
        (p.system + "\n---\n" + p.user).encode("utf-8")
    ).hexdigest()
    assert p.content_hash == expected


def test_each_agent_has_distinct_content_hash() -> None:
    # If translator and fixer ever produce the same hash something is very
    # wrong (or the agents are accidentally the same prompt).
    h_t = PromptRegistry.load("translator").content_hash
    h_f = PromptRegistry.load("fixer").content_hash
    h_r = PromptRegistry.load("reviewer").content_hash
    assert len({h_t, h_f, h_r}) == 3


# ── list_versions ───────────────────────────────────────────────────────


def test_list_versions_returns_sorted_list() -> None:
    versions = PromptRegistry.list_versions("translator")
    assert versions == sorted(versions)
    assert "1.0.0" in versions


def test_list_versions_unknown_agent_raises() -> None:
    with pytest.raises(PromptNotFoundError):
        PromptRegistry.list_versions("nonexistent-agent-xyz")


# ── Error paths ─────────────────────────────────────────────────────────


def test_load_unknown_agent_raises() -> None:
    with pytest.raises(PromptNotFoundError):
        PromptRegistry.load("nonexistent-agent-xyz")


def test_load_unknown_version_raises() -> None:
    with pytest.raises(PromptNotFoundError):
        PromptRegistry.load("translator", "9.9.9")


# ── Schema validation ───────────────────────────────────────────────────


def test_yaml_missing_required_keys_raises_schema_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Build a fake agent dir with a malformed v1.0.0.yaml.
    fake_root = tmp_path / "prompts"
    agent_dir = fake_root / "broken"
    agent_dir.mkdir(parents=True)
    (agent_dir / "v1.0.0.yaml").write_text(
        "version: \"1.0.0\"\nsystem: \"hello\"\n",  # missing 'user'
        encoding="utf-8",
    )
    # Point registry at the fake root and clear the cache.
    monkeypatch.setattr("app.agents.prompts.registry.PROMPTS_ROOT", fake_root)
    PromptRegistry._clear_cache_for_tests()
    try:
        with pytest.raises(PromptSchemaError, match="user"):
            PromptRegistry.load("broken", "1.0.0")
    finally:
        PromptRegistry._clear_cache_for_tests()


def test_yaml_version_mismatch_raises_schema_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_root = tmp_path / "prompts"
    agent_dir = fake_root / "mismatch"
    agent_dir.mkdir(parents=True)
    (agent_dir / "v1.0.0.yaml").write_text(
        "version: \"2.5.0\"\nsystem: \"x\"\nuser: \"y\"\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("app.agents.prompts.registry.PROMPTS_ROOT", fake_root)
    PromptRegistry._clear_cache_for_tests()
    try:
        with pytest.raises(PromptSchemaError, match="Version mismatch"):
            PromptRegistry.load("mismatch", "1.0.0")
    finally:
        PromptRegistry._clear_cache_for_tests()


# ── Migration fidelity (AC-6) ───────────────────────────────────────────


def test_translator_user_template_carries_all_expected_placeholders() -> None:
    # The legacy TRANSLATOR_USER_V1 contained these substitution keys.
    # If migration dropped any, downstream `.replace()` calls leave the
    # raw `{{var}}` literal in the LLM prompt — silent failure.
    p = PromptRegistry.load("translator")
    expected_placeholders = [
        "{{target_language}}",
        "{{audience}}",
        "{{domain}}",
        "{{risk_level}}",
        "{{language_instruction}}",
        "{{constraint_pack_json}}",
        "{{segments_json}}",
    ]
    for ph in expected_placeholders:
        assert ph in p.user, f"Missing placeholder in translator/v1.0.0: {ph!r}"


def test_fixer_user_template_carries_all_expected_placeholders() -> None:
    p = PromptRegistry.load("fixer")
    for ph in [
        "{{target_language}}",
        "{{constraint_pack_json}}",
        "{{segments_to_fix_json}}",
    ]:
        assert ph in p.user, f"Missing placeholder in fixer/v1.0.0: {ph!r}"


def test_reviewer_user_template_carries_all_expected_placeholders() -> None:
    p = PromptRegistry.load("reviewer")
    for ph in [
        "{{source_language}}",
        "{{target_language}}",
        "{{segments_json}}",
    ]:
        assert ph in p.user, f"Missing placeholder in reviewer/v1.0.0: {ph!r}"


# ── Frozen dataclass ────────────────────────────────────────────────────


def test_prompt_version_is_immutable() -> None:
    p = PromptRegistry.load("translator")
    # Frozen dataclass raises FrozenInstanceError (subclass of AttributeError)
    # on attribute assignment. Using setattr() rather than direct attribute
    # assignment so mypy doesn't need a type-suppression comment (which the
    # ratchet would flag as a regression).
    with pytest.raises((AttributeError, TypeError)):
        setattr(p, "system", "tampered")


# ── No more legacy-import survives ──────────────────────────────────────


def test_legacy_transmax_prompts_class_no_longer_importable() -> None:
    # Hard guard: the migration removed the inline-constant class. If a
    # caller silently re-introduces it, every other unit test in this file
    # would still pass; this one fails first.
    import app.agents.prompts as prompts_pkg
    assert not hasattr(prompts_pkg, "TransMaxPrompts"), (
        "TransMaxPrompts class should be removed in TMX-3201 — found it on the package."
    )
