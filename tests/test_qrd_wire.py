"""TMX-QRD-WIRE — fire the dead-but-tested QRD date/header checks (flag-gated).

The pure resolver `regulatory_profile_for_gate` carries the safety property
(off → None → byte-identical) without running the graph node; the end-to-end
firing is proven through `check_segment` (the gate node just passes the resolved
profile_id).
"""

from app.core.regulatory_profiles import regulatory_profile_for_gate
from app.services.quality_gate import QualityGateService


def test_disabled_returns_none_byte_identical():
    # Flag off: even a valid tag resolves to None, so the gate runs no QRD check.
    assert (
        regulatory_profile_for_gate(
            {"regulatory_profile": "EMA_SMPC_EN_GB"}, enabled=False
        )
        is None
    )


def test_enabled_known_profile_resolves():
    assert (
        regulatory_profile_for_gate(
            {"regulatory_profile": "EMA_SMPC_EN_GB"}, enabled=True
        )
        == "EMA_SMPC_EN_GB"
    )


def test_enabled_unknown_profile_is_none_not_fabricated():
    # A3: an unrecognised authority must fail to NO check, never a guessed default.
    assert (
        regulatory_profile_for_gate({"regulatory_profile": "NOPE_FAKE"}, enabled=True)
        is None
    )


def test_enabled_absent_tag_is_none():
    assert (
        regulatory_profile_for_gate({"archetype": "SAFETY_CRITICAL"}, enabled=True)
        is None
    )
    assert regulatory_profile_for_gate(None, enabled=True) is None


def test_non_string_tag_is_none_not_a_crash():
    # A malformed raw meta_json blob (dict/list/int) must no-op, not TypeError
    # into the gate (which would route to BLOCKED via the node's fail-safe).
    assert (
        regulatory_profile_for_gate({"regulatory_profile": {"x": 1}}, enabled=True)
        is None
    )
    assert (
        regulatory_profile_for_gate({"regulatory_profile": ["a"]}, enabled=True) is None
    )
    assert regulatory_profile_for_gate({"regulatory_profile": 7}, enabled=True) is None


def test_qrd_date_check_fires_with_resolved_profile():
    # End-to-end through the same call the gate node makes: a resolved EMA
    # profile (DD/MM/YYYY) makes an impossible MM/DD date fire.
    pid = regulatory_profile_for_gate(
        {"regulatory_profile": "EMA_SMPC_EN_GB"}, enabled=True
    )
    violations = QualityGateService().check_segment(
        "source", "Date: 01/30/2025", {}, "en", profile_id=pid
    )
    assert any(v["category"] == "FORMATTING_ERROR" for v in violations)


def test_qrd_checks_dead_when_flag_off():
    # The flag-off path: resolved profile is None -> check_segment runs NO QRD,
    # so the same bad date does NOT fire (byte-identical to today).
    pid = regulatory_profile_for_gate(
        {"regulatory_profile": "EMA_SMPC_EN_GB"}, enabled=False
    )
    violations = QualityGateService().check_segment(
        "source", "Date: 01/30/2025", {}, "en", profile_id=pid
    )
    assert not any(v["category"] == "FORMATTING_ERROR" for v in violations)


def test_jobprofilerequest_regulatory_profile_is_optional_and_flows():
    from app.schemas.api_v1 import JobProfileRequest

    # backwards-compatible: omitting the field still validates
    p1 = JobProfileRequest(
        archetype="SAFETY_CRITICAL", tier="TIER_A", modality="NARRATIVE"
    )
    assert p1.regulatory_profile is None

    # and when set it flows into model_dump() -> meta_json -> content_metadata
    p2 = JobProfileRequest(
        archetype="SAFETY_CRITICAL",
        tier="TIER_A",
        modality="NARRATIVE",
        regulatory_profile="EMA_SMPC_EN_GB",
    )
    assert p2.model_dump()["regulatory_profile"] == "EMA_SMPC_EN_GB"
