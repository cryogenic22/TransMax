"""TMX-MQM-5c — content/archetype → metric-profile resolution."""
import pytest

from app.core.metric_profiles.resolution import resolve_metric_profile, resolve_profile_id


@pytest.mark.parametrize(
    "md,expected",
    [
        ({"content_type": "smpc"}, "smpc_pil"),
        ({"content_type": "PIL"}, "smpc_pil"),
        ({"content_type": "icf"}, "icf"),
        ({"doc_type": "psur"}, "pv"),
        ({"content_type": "coa"}, "pro_coa"),
        ({"content_type": "promotional"}, "promo"),
        ({"archetype": "SAFETY_CRITICAL"}, "smpc_pil"),
        ({"archetype": "INFORMATIONAL"}, "promo"),
        ({"metric_profile": "pv"}, "pv"),
        ({}, "smpc_pil"),      # default
        (None, "smpc_pil"),
    ],
)
def test_resolve_profile_id(md, expected):
    assert resolve_profile_id(md) == expected


def test_explicit_override_beats_content_type():
    assert resolve_profile_id({"content_type": "icf", "metric_profile": "pv"}) == "pv"


def test_content_type_beats_archetype():
    assert resolve_profile_id({"content_type": "icf", "archetype": "SAFETY_CRITICAL"}) == "icf"


def test_resolve_metric_profile_returns_loaded_profile():
    p = resolve_metric_profile({"content_type": "icf"})
    assert p.profile_id == "icf"
    assert p.passing_threshold == 97


def test_unknown_profile_id_falls_back_to_default():
    p = resolve_metric_profile({"metric_profile": "does_not_exist"})
    assert p.profile_id == "smpc_pil"
