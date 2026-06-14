"""TMX-BB-STRICT — a locked (is_strict) Black-Book rule actually blocks."""
from app.core.defect_taxonomy import DefectSeverity
from app.services.quality_gate import get_quality_gate_service


def _check(constraints):
    # "device" → "dispositif"; target omits it. Neutral text that trips no other
    # critical gate (no numbers / frequency / negation / units / PII).
    return get_quality_gate_service().check_segment(
        source_text="Use the device",
        target_text="Utilisez l'appareil",
        constraints=constraints,
        target_lang="fr",
        source_lang="en",
    )


def test_strict_rule_violation_is_critical():
    defects = _check({"glossary": [
        {"source": "device", "target": "dispositif", "is_strict": True},
    ]})
    crit = [
        d for d in defects
        if d["severity"] == DefectSeverity.CRITICAL.value and "strict" in d["message"].lower()
    ]
    assert crit, f"expected a CRITICAL strict-rule defect, got {defects}"


def test_nonstrict_rule_violation_is_not_critical():
    defects = _check({"glossary": [
        {"source": "device", "target": "dispositif"},  # no is_strict
    ]})
    missing = [d for d in defects if "glossary term missing" in d["message"].lower()]
    assert missing, f"expected a glossary-missing defect, got {defects}"
    assert all(d["severity"] != DefectSeverity.CRITICAL.value for d in missing)
