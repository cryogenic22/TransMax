"""TMX-MQM-2 — content-type metric profile registry."""
import pytest

from app.core.defect_taxonomy import MqmDimension
from app.core.metric_profiles import (
    MetricProfile,
    MetricProfileNotFoundError,
    MetricProfileRegistry,
)


def test_all_five_vision_profiles_load():
    assert set(MetricProfileRegistry.list_profiles()) >= {
        "icf", "smpc_pil", "pv", "pro_coa", "promo",
    }


@pytest.mark.parametrize(
    "profile_id,pt,app_,evaluation",
    [
        ("icf", 97, 3, "full"),
        ("smpc_pil", 98, 2, "full"),
        ("pv", 97, 3, "full"),
        ("pro_coa", 97, 3, "full"),
        ("promo", 90, 10, "sampled"),
    ],
)
def test_profile_thresholds_match_vision_section_5_4(profile_id, pt, app_, evaluation):
    p = MetricProfileRegistry.load(profile_id)
    assert p.passing_threshold == pt
    assert p.acceptable_penalty_points == app_
    assert p.evaluation == evaluation
    assert p.critical_auto_fail is True
    assert p.sample_size_floor == 500


def test_smpc_error_type_weights():
    p = MetricProfileRegistry.load("smpc_pil")
    assert p.etw(MqmDimension.ACCURACY) == 3
    assert p.etw(MqmDimension.TERMINOLOGY) == 3
    assert p.etw(MqmDimension.DESIGN) == 2
    # Unpinned dimension falls back to the default weight.
    assert p.etw(MqmDimension.STYLE) == 1


def test_latest_resolves_and_content_hash_is_stable():
    p1 = MetricProfileRegistry.load("icf", "latest")
    p2 = MetricProfileRegistry.load("icf", "1.0.0")
    assert p1.version == "1.0.0"
    assert p1.content_hash == p2.content_hash
    assert len(p1.content_hash) == 64  # sha256 hex


def test_unknown_profile_raises():
    with pytest.raises(MetricProfileNotFoundError):
        MetricProfileRegistry.load("does_not_exist")


def test_profile_is_frozen_and_directly_constructable():
    # The frozen dataclass is constructable for tests/shadow profiles.
    p = MetricProfile(
        profile_id="t", version="0", display_name="t",
        passing_threshold=98, acceptable_penalty_points=2,
        evaluation="full", sample_size_floor=500, critical_auto_fail=False,
        error_type_weights={"default": 1},
    )
    assert p.etw(MqmDimension.ACCURACY) == 1
    with pytest.raises(Exception):
        p.passing_threshold = 50  # frozen
