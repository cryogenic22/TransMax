"""TMX-MQM-EVAL-CASES — the planted-defect recall gate over real fixtures (E13.S2 seed)."""
from app.core.defect_taxonomy import DefectSeverity, MqmDimension
from app.core.mqm_annotation import MqmAnnotation
from app.services.judge_eval import compute_judge_reliability, load_judge_gold


def _load():
    # TMX-MQM-EVAL-CI: one canonical loader, shared with the CI gate.
    return load_judge_gold()


def _critical(seg):
    return MqmAnnotation(segment_id=seg, dimension=MqmDimension.ACCURACY, severity=DefectSeverity.CRITICAL)


def test_fixture_has_planted_and_clean_cases():
    cases = _load()
    assert any(c["planted_critical"] for c in cases)
    assert any(not c["planted_critical"] for c in cases)


def test_perfect_judge_scores_full_recall():
    cases = _load()
    planted = [c["id"] for c in cases if c["planted_critical"]]
    judge = [_critical(c["id"]) for c in cases if c["planted_critical"]]
    m = compute_judge_reliability(planted, judge)
    assert m.recall == 1.0
    assert m.planted_total == len(planted)


def test_leniency_drift_is_caught_by_the_recall_gate():
    # A judge that drifts lenient and catches only one planted Critical must
    # score recall < 1.0 — the no-vacuous-green CI gate (E13.S2) would block it.
    cases = _load()
    planted = [c["id"] for c in cases if c["planted_critical"]]
    judge = [_critical(planted[0])]
    m = compute_judge_reliability(planted, judge)
    assert m.recall < 1.0
