"""TMX-MQM-EVAL-CI — the release-blocking judge-reliability gate.

Proves the no-vacuous-green guard: a missing/empty/lopsided gold set FAILS the
build (exit != 0) even in structure-only mode. The real-judge tier (recall
floor) is covered by the eval CI job when keys are present; here we cover the
integrity gate deterministically (no LLM).
"""

import json

from app.services.judge_eval import load_judge_gold
from scripts.judge_eval_gate import check_integrity, main


def _write(tmp_path, rows):
    p = tmp_path / "gold.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return p


def test_canonical_gold_loads_and_is_healthy():
    gold = load_judge_gold()
    assert len(gold) >= 6
    assert check_integrity(gold) == []


def test_structure_only_passes_on_real_gold():
    assert main(["check"]) == 0


def test_empty_gold_file_fails():
    import pathlib
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "empty.jsonl"
        p.write_text("", encoding="utf-8")
        assert main(["check", "--gold", str(p)]) == 2


def test_missing_gold_file_fails(tmp_path):
    assert main(["check", "--gold", str(tmp_path / "nope.jsonl")]) == 2


def test_planted_only_gold_fails(tmp_path):
    p = _write(
        tmp_path, [{"id": "a", "source": "x", "target": "y", "planted_critical": True}]
    )
    probs = check_integrity(load_judge_gold(p))
    assert any("no clean case" in x for x in probs)
    assert main(["check", "--gold", str(p)]) == 2


def test_clean_only_gold_fails(tmp_path):
    p = _write(
        tmp_path, [{"id": "a", "source": "x", "target": "y", "planted_critical": False}]
    )
    probs = check_integrity(load_judge_gold(p))
    assert any("no planted-Critical" in x for x in probs)
    assert main(["check", "--gold", str(p)]) == 2


def test_missing_required_key_fails(tmp_path):
    p = _write(
        tmp_path,
        [
            {"id": "a", "planted_critical": True},  # missing source/target
            {"id": "b", "source": "x", "target": "y", "planted_critical": False},
        ],
    )
    probs = check_integrity(load_judge_gold(p))
    assert any("missing keys" in x for x in probs)
    assert main(["check", "--gold", str(p)]) == 2


def test_corrupt_gold_line_fails_cleanly_not_crash(tmp_path):
    # A malformed gold line must report FAIL_INTEGRITY (exit 2), not raise a raw
    # JSONDecodeError traceback (red-team finding).
    p = tmp_path / "bad.jsonl"
    p.write_text(
        '{"id":"a","source":"x","target":"y","planted_critical":true}\n{ not json }\n',
        encoding="utf-8",
    )
    assert main(["check", "--gold", str(p)]) == 2


def _gold_2p_2c(tmp_path):
    rows = [
        {"id": "p1", "source": "a", "target": "b", "planted_critical": True},
        {"id": "p2", "source": "c", "target": "d", "planted_critical": True},
        {"id": "c1", "source": "e", "target": "f", "planted_critical": False},
        {"id": "c2", "source": "g", "target": "h", "planted_critical": False},
    ]
    return _write(tmp_path, rows), rows


def _mock_judge(monkeypatch, flagged_ids):
    from unittest.mock import AsyncMock

    from app.core.defect_taxonomy import DefectSeverity, MqmDimension
    from app.core.mqm_annotation import MqmAnnotation

    anns = [
        MqmAnnotation(
            segment_id=i,
            dimension=MqmDimension.ACCURACY,
            severity=DefectSeverity.CRITICAL,
        )
        for i in flagged_ids
    ]
    monkeypatch.setattr(
        "app.services.mqm_judge.judge_segments", AsyncMock(return_value=anns)
    )


def test_precision_floor_is_enforced_not_a_no_op(tmp_path, monkeypatch):
    # A flag-EVERYTHING judge has recall 1.0 but precision 0.5 — it must FAIL a
    # binding precision floor (with the old default 0.0 it passed vacuously).
    p, rows = _gold_2p_2c(tmp_path)
    _mock_judge(monkeypatch, [r["id"] for r in rows])  # flags all 4 (2 FPs)
    assert (
        main(["check", "--gold", str(p), "--require-judge", "--min-precision", "0.9"])
        == 1
    )


def test_good_judge_passes_the_real_judge_tier(tmp_path, monkeypatch):
    p, _ = _gold_2p_2c(tmp_path)
    _mock_judge(monkeypatch, ["p1", "p2"])  # exactly the planted Criticals
    assert main(["check", "--gold", str(p), "--require-judge"]) == 0
