"""TMX-MQM-1 — MQM annotation object + taxonomy reconciliation."""
import pytest

from app.core.defect_taxonomy import (
    SEVERITY_PENALTY_MULTIPLIER,
    Defect,
    DefectCategory,
    DefectSeverity,
    MqmDimension,
    dimension_for_category,
)
from app.core.mqm_annotation import MqmAnnotation, Span


def test_severity_gained_neutral_tier():
    # Additive: the four MQM severities all exist; legacy three unchanged.
    assert DefectSeverity.NEUTRAL.value == "NEUTRAL"
    assert {s.value for s in DefectSeverity} == {"CRITICAL", "MAJOR", "MINOR", "NEUTRAL"}


def test_spm_ladder_matches_mqm_council_defaults():
    assert SEVERITY_PENALTY_MULTIPLIER[DefectSeverity.NEUTRAL] == 0
    assert SEVERITY_PENALTY_MULTIPLIER[DefectSeverity.MINOR] == 1
    assert SEVERITY_PENALTY_MULTIPLIER[DefectSeverity.MAJOR] == 5
    assert SEVERITY_PENALTY_MULTIPLIER[DefectSeverity.CRITICAL] == 25


def test_seven_mqm_dimensions_present():
    assert len(list(MqmDimension)) == 7


@pytest.mark.parametrize(
    "category,expected",
    [
        (DefectCategory.NUMERIC_MISMATCH, MqmDimension.ACCURACY),
        (DefectCategory.FREQUENCY_MISMATCH, MqmDimension.ACCURACY),
        (DefectCategory.TERMINOLOGY, MqmDimension.TERMINOLOGY),
        (DefectCategory.STRUCTURE_ERROR, MqmDimension.DESIGN),
        (DefectCategory.FORMATTING_ERROR, MqmDimension.LOCALE),
        (DefectCategory.COMPLEXITY_WARNING, MqmDimension.AUDIENCE),
        (DefectCategory.SENTIMENT_SHIFT, MqmDimension.STYLE),
    ],
)
def test_category_maps_to_correct_dimension(category, expected):
    assert dimension_for_category(category) is expected


def test_dimension_fallback_is_accuracy_for_unknown():
    # Free-form / unknown category never raises — safest default in regulated content.
    assert dimension_for_category("SOME_FUTURE_CATEGORY") is MqmDimension.ACCURACY
    assert dimension_for_category("numeric_mismatch_typo") is MqmDimension.ACCURACY


def test_from_violation_reconciles_gate_dict():
    v = {
        "category": "NUMERIC_MISMATCH",
        "severity": "CRITICAL",
        "message": "10mg rendered as 100mg",
        "segment_id": "seg-7",
    }
    ann = MqmAnnotation.from_violation(v)
    assert ann.dimension is MqmDimension.ACCURACY
    assert ann.severity is DefectSeverity.CRITICAL
    assert ann.segment_id == "seg-7"
    assert ann.produced_by == "deterministic-gate"
    assert ann.explanation == "10mg rendered as 100mg"


def test_from_violation_normalises_lowercase_legacy_severity():
    ann = MqmAnnotation.from_violation({"category": "TERMINOLOGY", "severity": "major"})
    assert ann.severity is DefectSeverity.MAJOR


def test_from_violation_unknown_severity_defaults_major():
    ann = MqmAnnotation.from_violation({"category": "TERMINOLOGY", "severity": "weird"})
    assert ann.severity is DefectSeverity.MAJOR


def test_from_defect_reuses_existing_dataclass():
    d = Defect(
        category=DefectCategory.FREQUENCY_MISMATCH,
        severity=DefectSeverity.CRITICAL,
        message="twice daily -> once daily",
        segment_id="seg-3",
        suggestion="zweimal taeglich",
    )
    ann = MqmAnnotation.from_defect(d)
    assert ann.dimension is MqmDimension.ACCURACY
    assert ann.suggested_fix == "zweimal taeglich"
    assert ann.segment_id == "seg-3"


def test_critical_forces_is_auto_fail_true_denormalised():
    # Denormalised convenience kept consistent with severity (cond. 3): a
    # producer cannot set a Critical to is_auto_fail=False.
    ann = MqmAnnotation(
        dimension=MqmDimension.ACCURACY,
        severity=DefectSeverity.CRITICAL,
        is_auto_fail=False,
    )
    assert ann.is_auto_fail is True


def test_span_optional_offsets():
    s = Span(text="twice daily", start=120, end=131)
    assert s.start == 120 and s.end == 131
    assert Span(text="x").start is None
