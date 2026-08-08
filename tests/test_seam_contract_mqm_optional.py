"""TMX-SEAM-MQM-OPTIONAL — the contract must be able to say "no MQM score yet".

`SegmentResult.mqm` shipped as a REQUIRED `MqmSummary`. That makes the published
contract incapable of expressing the system's *actual current state*: the MQM
engine is shadow-only (`mqm_engine_enabled` has no consumer in application code)
and the live verdict is still the legacy count-based scorer, so no honest
MqmSummary exists for any segment today.

Why this is a defect rather than a detail:

1. reSCApe generates its typed client from `contract/openapi.json`. A required
   `mqm` tells that client the field is always present. When `SegmentResult` is
   eventually wired, the only ways to satisfy the published contract are to
   fabricate an `MqmSummary` or to break reSCApe's client — i.e. the schema
   would *force* the unearned-claim defect (ADR-0009 clause 5, seam invariant
   C-4) that this program has already had to fix four times.

2. It was caught empirically: TMX-SEAM-WIRE was instructed to leave `mqm` None
   and found it could not compose `SegmentResult` at all without fabricating
   one, so it extended `JobResult` instead. A contract a conforming implementer
   has to route around is a broken contract.

The fix is to make absence representable. `None` means "not scored" and becomes
a real `MqmSummary` at the TMX-MQM-5b cutover — no other field changes.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.api_v1 import (
    AuditRef,
    MqmSummary,
    ProvenanceRecord,
    SegmentResult,
    TranslationDisposition,
)


def _unscored_segment() -> SegmentResult:
    """A SegmentResult built the way a conforming implementer must build one
    today: every field populated from a real artefact, and no MQM score,
    because the shadow-only engine has produced none."""
    return SegmentResult(
        segment_id="seg-1",
        disposition=TranslationDisposition.REVIEW_REQUIRED,
        provenance=ProvenanceRecord(),
        audit=AuditRef(),
    )


def test_segment_result_can_represent_an_unscored_segment() -> None:
    """The regression: today's honest state must be expressible."""
    result = _unscored_segment()

    assert result.mqm is None, (
        "a segment the shadow-only MQM engine has not scored must serialise "
        "with mqm=None, not force the caller to fabricate an MqmSummary"
    )


def test_unscored_segment_survives_a_serialisation_round_trip() -> None:
    """None must survive to the wire — reSCApe reads JSON, not Python."""
    original = _unscored_segment()

    round_tripped = SegmentResult.model_validate(original.model_dump())

    assert round_tripped.mqm is None
    assert "mqm" in original.model_dump(), (
        "the key must be present-and-null rather than omitted, so a consumer "
        "can distinguish 'not scored' from 'field unknown to this version'"
    )


def test_a_real_mqm_summary_is_still_accepted() -> None:
    """Guard against fixing optionality by weakening the type."""
    scored = SegmentResult(
        segment_id="seg-1",
        disposition=TranslationDisposition.PASS,
        provenance=ProvenanceRecord(),
        audit=AuditRef(),
        mqm=MqmSummary(
            score=93.5,
            profile_id="smpc_pil",
            profile_version="1.0.0",
            critical_count=0,
            major_count=1,
            minor_count=2,
        ),
    )

    assert scored.mqm is not None
    assert scored.mqm.profile_id == "smpc_pil"
    assert scored.mqm.critical_count == 0


def test_mqm_summary_itself_stays_strict() -> None:
    """Optionality belongs on the *reference*, not inside MqmSummary.

    If a score exists at all, every component of it must be present — a
    half-populated MqmSummary would be its own unearned claim. Validated
    through `model_validate` so the partial payload is data, not a call the
    type checker would (correctly) reject at authoring time.
    """
    with pytest.raises(ValidationError):
        MqmSummary.model_validate({"score": 90.0})
