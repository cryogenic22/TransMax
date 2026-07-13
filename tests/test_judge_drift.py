"""TMX-MQM-EVAL-DRIFT — judge-reliability drift gate.

The shipped EVAL-CI gate enforces an ABSOLUTE floor (recall>=0.75). This adds
rolling-window drift detection (§6.10: "alert when agreement, recall or
precision regress beyond control limits over a rolling window; a regression
blocks release"). These tests pin:

  - the pure one-sided control-limit math (OK / DRIFT / INSUFFICIENT_HISTORY),
  - cold-start honesty (empty baseline → INSUFFICIENT_HISTORY, never fabricated),
  - that an *improvement* never fires (one-sided),
  - the `min_abs_drop` floor (no hair-trigger when std≈0) and the `k*std` band
    (no crying wolf when the judge is genuinely noisy),
  - that the CLI gate actually BLOCKS a regression with exit 3 (G3 completion),
    via a fake judge so no LLM key is needed.

This is judge META-EVAL drift — distinct from app/services/semantic_drift.py.
"""

from __future__ import annotations

import json

import pytest

from app.services.judge_eval import (
    JudgeReliability,
    detect_judge_drift,
    detect_metric_drift,
    load_drift_baseline,
)


# ── pure single-metric detector ──────────────────────────────────────────────


def test_insufficient_history_below_min():
    f = detect_metric_drift([0.95, 0.94, 0.96], current=0.10, min_history=5)
    assert f.status == "INSUFFICIENT_HISTORY"
    assert f.baseline_mean is None and f.lower_control_limit is None
    assert f.n_history == 3


def test_stable_window_no_drift():
    window = [0.95, 0.94, 0.96, 0.95, 0.95]
    f = detect_metric_drift(window, current=0.95)
    assert f.status == "OK"
    assert f.baseline_mean == pytest.approx(0.95, abs=0.01)


def test_sudden_drop_fires_drift():
    window = [0.95, 0.94, 0.96, 0.95, 0.95]
    f = detect_metric_drift(window, current=0.50)
    assert f.status == "DRIFT"
    assert f.current == 0.5
    assert "REGRESSED" in f.reason


def test_improvement_never_fires_one_sided():
    window = [0.80, 0.82, 0.79, 0.81, 0.80]
    f = detect_metric_drift(window, current=0.99)  # much better than the window
    assert f.status == "OK"


def test_min_abs_drop_floor_guards_hair_trigger():
    # A perfectly stable window (std == 0): a trivial 0.04 dip must NOT fire,
    # but a real 0.06 dip (> min_abs_drop=0.05) must.
    window = [0.95, 0.95, 0.95, 0.95, 0.95]
    assert detect_metric_drift(window, current=0.91).status == "OK"
    assert detect_metric_drift(window, current=0.89).status == "DRIFT"


def test_noisy_window_widens_the_band():
    # A genuinely noisy judge: a moderate dip stays within k*std (no crying wolf),
    # but a dip beyond the band fires.
    window = [0.60, 0.80, 0.95, 0.70, 0.90]  # mean 0.79, std ~0.128
    assert detect_metric_drift(window, current=0.45).status == "OK"
    assert detect_metric_drift(window, current=0.40).status == "DRIFT"


def test_lower_control_limit_is_mean_minus_threshold():
    window = [0.90, 0.90, 0.90, 0.90, 0.90]  # std 0 → threshold = min_abs_drop
    f = detect_metric_drift(window, current=0.90, min_abs_drop=0.05)
    assert f.baseline_mean == pytest.approx(0.90)
    assert f.lower_control_limit == pytest.approx(0.85)


# ── multi-metric judge drift ─────────────────────────────────────────────────


def test_detect_judge_drift_per_metric():
    history = [
        {"recall": 0.95, "precision": 1.0},
        {"recall": 0.96, "precision": 1.0},
        {"recall": 0.94, "precision": 1.0},
        {"recall": 0.95, "precision": 1.0},
        {"recall": 0.95, "precision": 1.0},
    ]
    findings = detect_judge_drift({"recall": 0.50, "precision": 1.0}, history)
    assert findings["recall"].status == "DRIFT"
    assert (
        findings["recall"].metric == "recall"
    )  # name stamped by the multi-metric layer
    assert findings["precision"].status == "OK"


def test_detect_judge_drift_skips_unmeasured_and_none():
    history = [
        {"recall": 0.95, "precision": None},
        {"recall": 0.96},
        {"recall": 0.94, "precision": 1.0},
        {"recall": 0.95, "precision": 1.0},
        {"recall": 0.95, "precision": 1.0},
    ]
    # precision absent from current ⇒ not scored at all
    findings = detect_judge_drift(
        {"recall": 0.95}, history, metrics=("recall", "precision")
    )
    assert set(findings) == {"recall"}
    # recall history has 5 usable points ⇒ a real verdict (not INSUFFICIENT)
    assert findings["recall"].status in {"OK", "DRIFT"}


# ── baseline loader / committed cold-start ───────────────────────────────────


def test_load_missing_baseline_is_honest_empty(tmp_path):
    b = load_drift_baseline(tmp_path / "nope.json")
    assert b == {"config": {}, "observations": []}


def test_committed_baseline_is_cold_start():
    b = load_drift_baseline()  # the canonical committed file
    assert (
        b["observations"] == []
    ), "committed baseline must ship empty (no fabricated history)"
    assert b["config"]["min_history"] >= 1


def test_cold_start_defers_to_floor():
    # With the empty committed window, every metric is INSUFFICIENT_HISTORY —
    # the gate must defer to the absolute floor, never fabricate OK/DRIFT.
    findings = detect_judge_drift({"recall": 0.10, "precision": 0.10}, [])
    assert all(f.status == "INSUFFICIENT_HISTORY" for f in findings.values())


# ── CLI gate: a regression actually blocks (exit 3) ──────────────────────────


def _write_baseline(tmp_path, recall_series, precision_series):
    obs = [
        {"recall": r, "precision": p} for r, p in zip(recall_series, precision_series)
    ]
    p = tmp_path / "drift_baseline.json"
    p.write_text(
        json.dumps(
            {
                "config": {"min_history": 5, "k": 3.0, "min_abs_drop": 0.05},
                "observations": obs,
            }
        ),
        encoding="utf-8",
    )
    return p


def _fake_judge(recall, precision):
    def _run(gold, args):
        return JudgeReliability(
            planted_total=4,
            planted_caught=round(recall * 4),
            recall=recall,
            false_positive_segments=0,
            precision=precision,
        )

    return _run


def test_gate_blocks_on_drift_exit_3(tmp_path, monkeypatch, capsys):
    import scripts.judge_eval_gate as gate

    baseline = _write_baseline(tmp_path, [0.95] * 5, [1.0] * 5)
    # The exact case drift exists to catch: recall 0.80 is ABOVE the absolute
    # floor (0.75) so EVAL-CI passes it, but it has eroded 0.15 below the 0.95
    # window — only the rolling-window gate blocks it.
    monkeypatch.setattr(gate, "_run_judge", _fake_judge(0.80, 1.0))
    code = gate.main(
        ["check", "--require-judge", "--check-drift", "--drift-baseline", str(baseline)]
    )
    out = json.loads(capsys.readouterr().out)
    assert code == 3
    assert out["result"] == "FAIL_DRIFT"
    assert out["drift"]["drift_detected"] is True
    assert out["drift"]["findings"]["recall"]["status"] == "DRIFT"


def test_gate_passes_when_no_drift(tmp_path, monkeypatch, capsys):
    import scripts.judge_eval_gate as gate

    baseline = _write_baseline(tmp_path, [0.95] * 5, [1.0] * 5)
    monkeypatch.setattr(gate, "_run_judge", _fake_judge(0.95, 1.0))
    code = gate.main(
        ["check", "--require-judge", "--check-drift", "--drift-baseline", str(baseline)]
    )
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["result"] == "PASS"
    assert out["drift"]["drift_detected"] is False


def test_gate_improvement_does_not_block(tmp_path, monkeypatch, capsys):
    import scripts.judge_eval_gate as gate

    baseline = _write_baseline(tmp_path, [0.80] * 5, [0.90] * 5)
    monkeypatch.setattr(
        gate, "_run_judge", _fake_judge(0.99, 1.0)
    )  # better than window
    code = gate.main(
        ["check", "--require-judge", "--check-drift", "--drift-baseline", str(baseline)]
    )
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["drift"]["drift_detected"] is False


def test_gate_structure_only_skips_drift(capsys):
    import scripts.judge_eval_gate as gate

    code = gate.main(
        ["check", "--check-drift"]
    )  # no --require-judge, committed gold + baseline
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["result"] == "PASS_STRUCTURE_ONLY"
    assert out["drift"]["status"] == "SKIPPED_NO_CURRENT"


def test_gate_malformed_baseline_is_integrity_failure(tmp_path, monkeypatch, capsys):
    import scripts.judge_eval_gate as gate

    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(gate, "_run_judge", _fake_judge(0.95, 1.0))
    code = gate.main(
        ["check", "--require-judge", "--check-drift", "--drift-baseline", str(bad)]
    )
    out = json.loads(capsys.readouterr().out)
    assert code == 2
    assert out["result"] == "FAIL_INTEGRITY"


# ── drift-update: deliberate, PR-reviewed history accrual (AC-8) ──────────────
# The maintainer command that grows the window. It must APPEND (never clobber)
# and must preserve the committed `_doc`/config — the baseline is the regulatory
# evidence window, so a silent clobber there is exactly the corruption A3 guards.


def test_drift_update_appends_and_preserves_doc(tmp_path, monkeypatch, capsys):
    import scripts.judge_eval_gate as gate
    from app.core.config import settings

    p = tmp_path / "drift_baseline.json"
    p.write_text(
        json.dumps(
            {
                "_doc": "NEVER hand-edit observations to fabricate history",
                "config": {"metrics": ["recall", "precision"], "min_history": 5},
                "observations": [{"label": "seed", "recall": 0.95, "precision": 1.0}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-dummy")
    monkeypatch.setattr(gate, "_run_judge", _fake_judge(0.90, 1.0))
    code = gate.main(["drift-update", "--label", "run-2", "--drift-baseline", str(p)])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["result"] == "APPENDED"
    assert out["history_count"] == 2

    written = json.loads(p.read_text(encoding="utf-8"))
    # the committed doc + config survive the write (not clobbered)
    assert written["_doc"] == "NEVER hand-edit observations to fabricate history"
    assert written["config"]["min_history"] == 5
    # the new observation is APPENDED after the seed, carrying the real judge result
    assert [o["label"] for o in written["observations"]] == ["seed", "run-2"]
    assert written["observations"][-1]["recall"] == 0.90


def test_drift_update_requires_keys(tmp_path, monkeypatch, capsys):
    import scripts.judge_eval_gate as gate
    from app.core.config import settings

    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    # without keys the judge must NEVER run — the guard returns before that
    monkeypatch.setattr(
        gate, "_run_judge", lambda *a, **k: pytest.fail("judge ran without keys")
    )
    code = gate.main(
        ["drift-update", "--label", "x", "--drift-baseline", str(tmp_path / "b.json")]
    )
    out = json.loads(capsys.readouterr().out)
    assert code == 2
    assert out["result"] == "NO_KEYS"
