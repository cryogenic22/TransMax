"""TMX-MQM-EVAL — judge-reliability metric (planted-defect recall + precision)."""
from app.core.defect_taxonomy import DefectSeverity, MqmDimension
from app.core.mqm_annotation import MqmAnnotation
from app.services.judge_eval import compute_judge_reliability


def _judge_critical(seg):
    return MqmAnnotation(segment_id=seg, dimension=MqmDimension.ACCURACY, severity=DefectSeverity.CRITICAL)


def _judge_minor(seg):
    return MqmAnnotation(segment_id=seg, dimension=MqmDimension.STYLE, severity=DefectSeverity.MINOR)


def test_perfect_recall_and_precision():
    planted = ["s1", "s2"]
    judge = [_judge_critical("s1"), _judge_critical("s2")]
    m = compute_judge_reliability(planted, judge)
    assert m.recall == 1.0
    assert m.precision == 1.0
    assert m.planted_caught == 2


def test_missed_planted_defect_drops_recall():
    planted = ["s1", "s2"]
    judge = [_judge_critical("s1")]  # missed s2 — the gate-failing case
    m = compute_judge_reliability(planted, judge)
    assert m.recall == 0.5
    assert m.planted_caught == 1


def test_over_flagging_drops_precision():
    planted = ["s1"]
    judge = [_judge_critical("s1"), _judge_critical("s9")]  # s9 not planted = false positive
    m = compute_judge_reliability(planted, judge)
    assert m.recall == 1.0
    assert m.false_positive_segments == 1
    assert m.precision == 0.5


def test_minor_annotations_do_not_count_as_critical_catches():
    planted = ["s1"]
    judge = [_judge_minor("s1")]  # judge flagged it, but only Minor — planted Critical missed
    m = compute_judge_reliability(planted, judge)
    assert m.recall == 0.0


def test_no_planted_defects_is_perfect_recall():
    m = compute_judge_reliability([], [])
    assert m.recall == 1.0
    assert m.precision == 1.0
