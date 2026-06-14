"""TMX-MQM-3 — pure MQM-2.0 engine.

Spec-binding tests pin the engine to the LangOps Platform Vision §5.5 worked
examples (RQS=99 for 10 minors/1000w; the SmPC and Promo CQS boundaries). The
condition-driven tests pin the three review conditions baked into the design:
auto-fail is engine-derived and non-overridable (cond. 3); insufficient_sample
is separate from the pass/fail verdict (cond. 2).
"""
from app.core.defect_taxonomy import DefectSeverity, MqmDimension
from app.core.metric_profiles import MetricProfile, MetricProfileRegistry
from app.core.mqm_annotation import MqmAnnotation
from app.services.mqm_engine import score, score_from_violations


def _minors(n: int):
    """n MINOR linguistic annotations (ETW defaults to 1 in every profile)."""
    return [
        MqmAnnotation(dimension=MqmDimension.LINGUISTIC, severity=DefectSeverity.MINOR)
        for _ in range(n)
    ]


# --------------------------------------------------------------------------- #
# Spec-binding: the vision's own worked numbers (§5.5)                         #
# --------------------------------------------------------------------------- #
def test_rqs_spec_example_ten_minors_in_1000_words_is_99():
    s = score(_minors(10), MetricProfileRegistry.load("icf"), ewc=1000)
    assert s.apt == 10
    assert s.pwpt == 0.01
    assert s.rqs == 99.0


def test_promo_cqs_boundary_pass_then_fail():
    promo = MetricProfileRegistry.load("promo")  # PT=90, APP=10 -> SF=1
    at_boundary = score(_minors(10), promo, ewc=1000)   # NPT=10 -> CQS=90
    assert at_boundary.cqs == 90.0 and at_boundary.passed is True
    over = score(_minors(20), promo, ewc=1000)          # NPT=20 -> CQS=80
    assert over.cqs == 80.0 and over.passed is False


def test_smpc_cqs_boundary_pass_then_fail():
    smpc = MetricProfileRegistry.load("smpc_pil")  # PT=98, APP=2 -> SF=1
    ok = score(_minors(2), smpc, ewc=1000)              # NPT=2 -> CQS=98
    assert ok.cqs == 98.0 and ok.passed is True
    bad = score(_minors(3), smpc, ewc=1000)             # NPT=3 -> CQS=97
    assert bad.cqs == 97.0 and bad.passed is False


# --------------------------------------------------------------------------- #
# Cond. 3 — Critical auto-fail is engine-derived and NON-overridable          #
# --------------------------------------------------------------------------- #
def test_critical_auto_fail_cannot_be_bought_back_by_a_high_score():
    crit = [MqmAnnotation(dimension=MqmDimension.ACCURACY, severity=DefectSeverity.CRITICAL)]
    smpc = MetricProfileRegistry.load("smpc_pil")  # critical_auto_fail = true
    s = score(crit, smpc, ewc=100_000)             # huge EWC -> CQS ~ 100 (>= PT)
    assert s.cqs >= smpc.passing_threshold         # score alone would pass...
    assert s.critical_auto_fail is True
    assert s.passed is False                       # ...but the Critical auto-fails it
    assert "auto-fail" in s.deciding_reason


def test_auto_fail_is_governed_by_profile_flag_not_annotation():
    crit = [MqmAnnotation(dimension=MqmDimension.ACCURACY, severity=DefectSeverity.CRITICAL)]
    no_autofail = MetricProfile(
        profile_id="t", version="0", display_name="t",
        passing_threshold=98, acceptable_penalty_points=2,
        evaluation="full", sample_size_floor=500, critical_auto_fail=False,
        error_type_weights={"default": 1},
    )
    s = score(crit, no_autofail, ewc=100_000)
    assert s.critical_auto_fail is False
    assert s.passed is True  # same Critical, auto-fail disabled -> threshold governs


def test_engine_ignores_annotation_is_auto_fail_flag():
    # A MAJOR annotation with is_auto_fail wrongly True must NOT auto-fail:
    # the engine derives auto-fail from severity==CRITICAL only (cond. 3).
    ann = MqmAnnotation(dimension=MqmDimension.ACCURACY, severity=DefectSeverity.MAJOR)
    object.__setattr__(ann, "is_auto_fail", True)  # force the non-authoritative flag
    s = score([ann], MetricProfileRegistry.load("smpc_pil"), ewc=1000)
    assert s.critical_auto_fail is False
    assert s.critical_count == 0


# --------------------------------------------------------------------------- #
# Cond. 2 — insufficient_sample is SEPARATE from the quality verdict (§5.6)   #
# --------------------------------------------------------------------------- #
def test_short_high_scoring_doc_passes_but_is_flagged_not_trusted():
    smpc = MetricProfileRegistry.load("smpc_pil")  # floor 500
    s = score([], smpc, ewc=80)                    # clean, but 80 words
    assert s.passed is True                        # quality verdict is honest
    assert s.insufficient_sample is True           # ...and flagged for routing
    assert s.confidence_interval is not None
    lo, hi = s.confidence_interval
    assert lo <= s.cqs <= hi
    assert "human review" in s.deciding_reason


def test_sufficient_sample_has_no_interval():
    s = score([], MetricProfileRegistry.load("smpc_pil"), ewc=1000)
    assert s.insufficient_sample is False
    assert s.confidence_interval is None


# --------------------------------------------------------------------------- #
# Engine properties: purity, determinism, the reconciliation adapter          #
# --------------------------------------------------------------------------- #
def test_determinism_same_inputs_same_output():
    icf = MetricProfileRegistry.load("icf")
    a = score(_minors(5), icf, ewc=900)
    b = score(_minors(5), icf, ewc=900)
    assert a == b  # frozen dataclass value-equality


def test_etw_weights_amplify_penalty_by_dimension():
    smpc = MetricProfileRegistry.load("smpc_pil")  # Accuracy ETW=3
    acc = [MqmAnnotation(dimension=MqmDimension.ACCURACY, severity=DefectSeverity.MAJOR)]
    s = score(acc, smpc, ewc=1000)
    # ETPT = ETW(3) * SPM_major(5) = 15
    assert s.apt == 15
    assert s.etpt_by_dimension["Accuracy"] == 15


def test_score_from_violations_adapter_reconciles_gate_output():
    violations = [
        {"category": "NUMERIC_MISMATCH", "severity": "CRITICAL", "message": "10->100mg"},
    ]
    s = score_from_violations(violations, MetricProfileRegistry.load("smpc_pil"), ewc=500)
    assert s.critical_count == 1
    assert s.critical_auto_fail is True
    assert s.passed is False


def test_zero_ewc_does_not_divide_by_zero():
    s = score(_minors(1), MetricProfileRegistry.load("icf"), ewc=0)
    assert s.insufficient_sample is True
    assert s.cqs is not None  # no exception
