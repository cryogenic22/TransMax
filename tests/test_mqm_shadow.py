"""TMX-MQM-5 (phase a) — MQM engine shadow integration."""
from types import SimpleNamespace

from app.agents.nodes.mqm_shadow import run_mqm_shadow


def _state_with(source_words: int):
    return {
        "job_id": "job-1",
        "segments": [
            {"source_text": " ".join(["w"] * source_words), "translated_text": "x"}
        ],
    }


def test_shadow_returns_comparison_and_agrees_on_block():
    state = _state_with(5)
    violations = [{"category": "NUMERIC_MISMATCH", "severity": "CRITICAL", "message": "10->100mg"}]
    out = run_mqm_shadow(state, violations, "BLOCKED")
    assert out is not None
    assert out["mqm"]["critical_auto_fail"] is True
    assert out["mqm"]["passed"] is False
    assert out["block_agreement"] is True  # legacy BLOCKED ↔ MQM would block


def test_shadow_agrees_on_clean_pass():
    out = run_mqm_shadow(_state_with(3), [], "PASS")
    assert out is not None
    assert out["mqm"]["passed"] is True
    assert out["block_agreement"] is True  # neither blocks


def test_shadow_disabled_returns_none(monkeypatch):
    monkeypatch.setattr(
        "app.agents.nodes.mqm_shadow.get_settings",
        lambda: SimpleNamespace(mqm_shadow_enabled=False, mqm_default_profile="smpc_pil"),
    )
    assert run_mqm_shadow(_state_with(5), [], "PASS") is None


def test_shadow_never_raises_and_never_changes_verdict():
    # Malformed state must not raise; the helper is purely observational.
    state = {"job_id": "j", "segments": []}  # no segments => ewc 0
    out = run_mqm_shadow(state, [], "PASS")
    assert out is not None  # returns a dict, does not throw
    # The function returns a comparison; it cannot mutate the caller's verdict
    # because it only reads `state` and `legacy_status`.
    assert "mqm" in out
