"""en->de critical-safety golden suite.

Loads `data/en_de/critical_safety.jsonl` and asserts that:
- canonical translations produce NO critical defects of the listed categories.
- tampered translations produce the EXPECTED critical defect.

This suite gates the v3.0 release: critical-defect rate on the canonical set
must be 0; expected defects on the tampered set must fire 100%.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.quality_gate import QualityGateService

DATA = Path(__file__).parent / "data" / "en_de" / "critical_safety.jsonl"


def _load() -> list[dict]:
    with DATA.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _ids(cases: list[dict]) -> list[str]:
    return [c["id"] for c in cases]


@pytest.mark.parametrize("case", _load(), ids=_ids(_load()))
def test_eval_case(quality_gate: QualityGateService, case: dict) -> None:
    """One assertion per case; runs the deterministic gates only."""
    defects = quality_gate.check_segment(
        source_text=case["source"],
        target_text=case["target"],
        constraints={"glossary": [], "tm_matches": []},
        target_lang="de",
        source_lang="en",
    )

    expected = case["expected_defects"]
    actual_categories_critical = sorted(
        d["category"] for d in defects if d.get("severity") == "CRITICAL"
    )
    expected_categories_critical = sorted(
        e["category"] for e in expected if e.get("severity") == "CRITICAL"
    )

    if case["kind"] == "canonical":
        # Canonical: no critical defects of the families we care about.
        assert not actual_categories_critical, (
            f"[{case['id']}] canonical translation produced unexpected CRITICAL defects: "
            f"{actual_categories_critical}. Rationale: {case['rationale']}"
        )

    elif case["kind"] == "tampered":
        # Tampered: every expected category must appear among actual.
        for expected_cat in expected_categories_critical:
            assert expected_cat in actual_categories_critical, (
                f"[{case['id']}] tampered translation missed expected CRITICAL defect "
                f"{expected_cat}. Actual CRITICAL categories: {actual_categories_critical}. "
                f"Rationale: {case['rationale']}"
            )

    else:
        pytest.fail(f"[{case['id']}] unknown kind: {case['kind']!r}")


def test_corpus_well_formed() -> None:
    """Sanity: every case has the required fields, kinds are valid, no duplicate ids."""
    cases = _load()
    seen: set[str] = set()
    valid_kinds = {"canonical", "tampered"}
    for c in cases:
        assert "id" in c and "kind" in c and "source" in c and "target" in c, c
        assert c["kind"] in valid_kinds, f"{c['id']}: invalid kind {c['kind']!r}"
        assert c["id"] not in seen, f"duplicate id {c['id']}"
        seen.add(c["id"])
        assert isinstance(c.get("expected_defects", []), list)
    assert len(cases) >= 6, "starter corpus must cover at least 6 cases"
