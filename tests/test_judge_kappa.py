"""TMX-MQM-EVAL-KAPPA — Cohen's kappa primitive + per-segment label helpers.

Pure math + degenerate-case honesty (A3: no fabricated agreement). The expected
kappa values below are computed by hand in the worksheet design section.
"""

from app.services.judge_eval import binary_severity_label_map, cohen_kappa


def test_perfect_agreement_is_kappa_one():
    a = {"1": "CRITICAL", "2": "OK"}
    b = {"1": "CRITICAL", "2": "OK"}
    r = cohen_kappa(a, b)
    assert r.kappa == 1.0
    assert r.observed_agreement == 1.0
    assert r.n_items == 2


def test_chance_level_agreement_is_kappa_zero():
    # p_o = 0.5, p_e = 0.5 -> kappa = 0.0 (agreement no better than chance).
    a = {"1": "C", "2": "C", "3": "O", "4": "O"}
    b = {"1": "C", "2": "O", "3": "C", "4": "O"}
    r = cohen_kappa(a, b)
    assert r.kappa == 0.0


def test_systematic_disagreement_is_negative_kappa():
    a = {"1": "C", "2": "C", "3": "O", "4": "O"}
    b = {"1": "O", "2": "O", "3": "C", "4": "C"}
    r = cohen_kappa(a, b)
    assert r.kappa is not None and r.kappa < 0.0


def test_no_shared_items_is_undefined_not_fabricated():
    # The honest case (A3): raters labelled disjoint items -> kappa must be None,
    # never a fabricated 0.0 or 1.0.
    r = cohen_kappa({"1": "OK"}, {"2": "OK"})
    assert r.kappa is None
    assert r.n_items == 0


def test_single_category_full_agreement_is_kappa_one():
    # Both raters call everything OK: (1 - p_e) == 0; agreement is trivial -> 1.0.
    r = cohen_kappa({"1": "OK", "2": "OK"}, {"1": "OK", "2": "OK"})
    assert r.kappa == 1.0


def test_only_inner_join_is_scored():
    a = {"1": "CRITICAL", "2": "OK", "3": "CRITICAL"}
    b = {"1": "CRITICAL", "2": "OK"}  # never saw segment 3
    r = cohen_kappa(a, b)
    assert r.n_items == 2  # segment 3 is not counted as (dis)agreement


def test_binary_label_map_marks_unflagged_as_explicit_ok():
    labels = binary_severity_label_map(["s1", "s2", "s3"], ["s2"])
    assert labels == {"s1": "OK", "s2": "CRITICAL", "s3": "OK"}
