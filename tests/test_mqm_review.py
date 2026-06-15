"""TMX-MQM-6 — ensemble aggregation + conservation constraint (pure)."""
from app.core.defect_taxonomy import DefectSeverity, MqmDimension
from app.core.mqm_annotation import MqmAnnotation, Span
from app.services.mqm_review import aggregate_ensemble, enforce_conservation


def _ann(seg, dim, sev, target=None):
    return MqmAnnotation(
        segment_id=seg, dimension=dim, severity=sev,
        target_span=Span(text=target) if target else None,
    )


# --- ensemble ---
def test_ensemble_takes_most_severe_and_escalates_on_disagreement():
    j1 = [_ann("s1", MqmDimension.ACCURACY, DefectSeverity.MINOR, "X")]
    j2 = [_ann("s1", MqmDimension.ACCURACY, DefectSeverity.CRITICAL, "X")]
    r = aggregate_ensemble([j1, j2])
    assert len(r.merged) == 1
    assert r.merged[0].severity is DefectSeverity.CRITICAL  # most severe, never averaged
    assert r.escalate is True


def test_ensemble_full_agreement_does_not_escalate():
    j1 = [_ann("s1", MqmDimension.ACCURACY, DefectSeverity.MAJOR, "X")]
    j2 = [_ann("s1", MqmDimension.ACCURACY, DefectSeverity.MAJOR, "X")]
    r = aggregate_ensemble([j1, j2])
    assert r.escalate is False


def test_ensemble_one_judge_missing_a_span_escalates():
    j1 = [_ann("s1", MqmDimension.ACCURACY, DefectSeverity.CRITICAL, "X")]
    j2 = []
    r = aggregate_ensemble([j1, j2])
    assert r.escalate is True
    assert len(r.merged) == 1


# --- conservation ---
_ORIG = "Take two tablets twice daily with water."


def test_conservation_accepts_edit_within_flagged_span():
    s = _ORIG.index("twice daily"); e = s + len("twice daily")
    revised = "Take two tablets once daily with water."
    r = enforce_conservation(_ORIG, revised, [(s, e)])
    assert r.accepted is True


def test_conservation_rejects_edit_outside_flagged_span():
    s = _ORIG.index("twice daily"); e = s + len("twice daily")
    revised = "Take three tablets once daily with water."  # 'two'→'three' is out of scope
    r = enforce_conservation(_ORIG, revised, [(s, e)])
    assert r.accepted is False
    assert r.out_of_scope_chunks
