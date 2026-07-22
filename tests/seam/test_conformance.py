"""TMX-SEAM-CONFORMANCE — the seam conformance suite (CROSS-REPO-PROTOCOL Rule 4).

Rule 4 defines nine standing invariants (C-1..C-9) that must hold across the
TransMax <-> reSCApe seam. The canonical suite runs against a LIVE pair (this
TransMax service + a pinned reSCApe container) and forbids mocking the
counterpart. This worktree has no reSCApe counterpart to run against, so this
module implements each invariant as an executable assertion against the
CONTRACT (`app.schemas.api_v1`) and the ENGINE-SIDE behaviour that IS
available in-process (`transmax_sdk`, `app.api.v1.translations`) — never a
mock standing in for reSCApe itself.

Coverage, honestly declared (see the meta-suite at the bottom, which fails
the build if this table silently drifts from what is actually registered):

  C-2  COVERED  - typed ProviderUnavailableError / InvalidModelResponseError
  C-4  COVERED  - provenance defaults to None, never "MT"/"transmax_ai"
  C-5  COVERED  - a TM-exact segment still runs the deterministic gates
  C-7  COVERED  - duplicate request_id yields one job (DB-enforced today)
  C-9  PENDING  - language_tier field exists + defaults None; no tiering
                  engine exists yet (TMX-LANG-TIERS, unbuilt)
  C-1  SKIPPED  - needs a live reSCApe pair; blocked on TMX-SEAM-CLIENT
  C-3  SKIPPED  - needs TMX-LANGDETECT-HOLD (READY, unbuilt)
  C-6  SKIPPED  - needs a live pair + signature-reference wiring (unfiled)
  C-8  SKIPPED  - needs a live pair to independently re-verify the chain

CRITICAL HONESTY RULE: a suite that can report vacuous green by silently
skipping everything is worse than no suite. `TestSeamSuiteHonesty` below
mechanically checks that every COVERED invariant has at least one
non-skipped registered test, that PENDING count matches a declared
constant, and that every SKIPPED invariant carries a named blocking ticket
— so silently skipping everything fails the build, it does not pass it.
"""

from __future__ import annotations

import json
from types import ModuleType
from typing import Callable, Dict, FrozenSet, List, Optional

import pytest

from app.schemas.api_v1 import ProvenanceRecord
from transmax_sdk.errors import (
    InvalidModelResponseError,
    ProviderUnavailableError,
    TransMaxSDKError,
)
from transmax_sdk.memory.tm import VectorTranslationMemory
from transmax_sdk.pipeline.pipeline import DefaultTranslationPipeline
from transmax_sdk.types import TranslationRequest, TranslationSegment

# ---------------------------------------------------------------------------
# Invariant registry — the honesty mechanism.
# ---------------------------------------------------------------------------

SKIPPED_INVARIANTS: FrozenSet[str] = frozenset({"C-1", "C-3", "C-6", "C-8"})
COVERED_INVARIANTS: FrozenSet[str] = frozenset({"C-2", "C-4", "C-5", "C-7", "C-9"})
PENDING_INVARIANTS: FrozenSet[str] = frozenset({"C-9"})
DECLARED_PENDING_COUNT = 1
ALL_INVARIANTS: FrozenSet[str] = frozenset(f"C-{i}" for i in range(1, 10))

INVARIANT_COVERAGE: Dict[str, List[Callable[..., object]]] = {}
SKIP_COVERAGE: Dict[str, List[Callable[..., object]]] = {}


def covers(invariant_id: str) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Register `fn` as a real (non-skipped) test of `invariant_id`."""

    def decorator(fn: Callable[..., object]) -> Callable[..., object]:
        INVARIANT_COVERAGE.setdefault(invariant_id, []).append(fn)
        return fn

    return decorator


def skip_covers(
    invariant_id: str, *, reason: str
) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Register `fn` as the documented-but-skipped test of `invariant_id`.

    Applies `pytest.mark.skip(reason=...)` so the test body is committed
    (documents intent) but never executed — and is registered so the meta
    suite can verify the skip carries a named blocking ticket.
    """

    def decorator(fn: Callable[..., object]) -> Callable[..., object]:
        SKIP_COVERAGE.setdefault(invariant_id, []).append(fn)
        return pytest.mark.skip(reason=reason)(fn)

    return decorator


# ---------------------------------------------------------------------------
# Shared fixtures / helpers for the pipeline-level invariants.
# ---------------------------------------------------------------------------


def _one_segment_request() -> TranslationRequest:
    return TranslationRequest(
        segments=[TranslationSegment(segment_id="s1", source_text="Take 10mg daily")],
        source_lang="en",
        target_lang="fr",
    )


class _CannedLLMProvider:
    """Minimal LLMProviderProtocol stand-in returning a fixed payload.

    This is a stand-in for TransMax's OWN LLM provider dependency, not for
    reSCApe — Rule 4 forbids mocking the counterpart, not mocking a provider
    TransMax itself would otherwise call.
    """

    def __init__(self, content: str) -> None:
        self._content = content

    @property
    def name(self) -> str:
        return "canned"

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, str]:
        return {"content": self._content, "model": "canned-1"}


# ---------------------------------------------------------------------------
# C-2 — no provider / invalid model response => typed error, never fabricated.
# ---------------------------------------------------------------------------


class TestC2FailClosedOnProviderAndModelResponse:
    @covers("C-2")
    @pytest.mark.asyncio
    async def test_no_provider_configured_raises_typed_provider_unavailable(
        self,
    ) -> None:
        """No LLM provider anywhere in the pipeline -> typed
        PROVIDER_UNAVAILABLE, never a fabricated `[target] source` result."""
        pipeline = DefaultTranslationPipeline()
        with pytest.raises(ProviderUnavailableError) as exc_info:
            await pipeline.execute(_one_segment_request())
        assert exc_info.value.code == "PROVIDER_UNAVAILABLE"
        assert isinstance(exc_info.value, TransMaxSDKError)

    @covers("C-2")
    @pytest.mark.asyncio
    async def test_unparseable_model_response_raises_typed_invalid_model_response(
        self,
    ) -> None:
        """An unparseable model response is a typed INVALID_MODEL_RESPONSE,
        never a silently dropped segment."""
        pipeline = DefaultTranslationPipeline(
            llm_provider=_CannedLLMProvider("not json {{{")
        )
        with pytest.raises(InvalidModelResponseError) as exc_info:
            await pipeline.execute(_one_segment_request())
        assert exc_info.value.code == "INVALID_MODEL_RESPONSE"
        assert isinstance(exc_info.value, TransMaxSDKError)


# ---------------------------------------------------------------------------
# C-4 — no response can carry a provenance value the engine did not earn.
# ---------------------------------------------------------------------------


class TestC4NoUnearnedProvenance:
    @covers("C-4")
    def test_fresh_provenance_record_defaults_to_none_never_a_plausible_string(
        self,
    ) -> None:
        """A `ProvenanceRecord` backed by no artefact must default every
        field to None — never a plausible-looking string, and specifically
        never the two known unearned-provenance values ("MT", "transmax_ai")
        this program's ADR-0009 postmortem names."""
        record = ProvenanceRecord()
        dumped = record.model_dump()
        assert dumped, "ProvenanceRecord.model_dump() returned no fields to check"
        for field_name, value in dumped.items():
            assert value is None, f"{field_name} defaulted to {value!r}, not None"
            assert value != "MT"
            assert value != "transmax_ai"

    @covers("C-4")
    @pytest.mark.asyncio
    async def test_untranslated_segment_is_labelled_untranslated_never_mt(
        self,
    ) -> None:
        """A segment with no earned translation (a valid-but-empty model
        response) is labelled UNTRANSLATED along the real code path — never
        defaulted to the earned-only "MT" provenance value."""
        payload = json.dumps({"segments": []})
        pipeline = DefaultTranslationPipeline(
            llm_provider=_CannedLLMProvider(payload)
        )
        result = await pipeline.execute(_one_segment_request())
        seg = result.segments[0]
        assert seg.translated_text == ""
        assert seg.translation_source == "UNTRANSLATED"
        assert seg.translation_source != "MT"


# ---------------------------------------------------------------------------
# C-5 — a TM-bound segment still runs the deterministic gates.
# ---------------------------------------------------------------------------


class TestC5TmBindingDoesNotSkipGates:
    @covers("C-5")
    @pytest.mark.asyncio
    async def test_tm_exact_segment_still_runs_the_numeric_gate(self) -> None:
        """ADR-0009 clause 4 / clause 5: binding skips the model, never the
        checks. Store a TM entry whose target drops a source number, then
        confirm the ghost-number deterministic gate still fires on the
        TM-matched segment even though no LLM call ever happened."""
        tm = VectorTranslationMemory()
        tm.store("Take 10mg daily", "Prendre 5mg par jour", "en", "fr")
        pipeline = DefaultTranslationPipeline(tm=tm)
        result = await pipeline.execute(_one_segment_request())
        seg = result.segments[0]
        assert seg.translation_source == "TM_EXACT"
        assert any(defect.category == "NUMERIC_MISMATCH" for defect in seg.defects), (
            "a TM-bound segment must still run the deterministic gates — "
            "binding skipped the model correctly but appears to have also "
            "skipped the checks"
        )


# ---------------------------------------------------------------------------
# C-7 — same request_id twice => one job, one set of side effects.
# ---------------------------------------------------------------------------


class TestC7RequestIdIdempotency:
    @covers("C-7")
    def test_duplicate_request_id_yields_one_job_not_two(
        self, fresh_engine_for_db: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Enforced today at `app/api/v1/translations.py`'s
        `Document.client_request_id` lookup. Exercised through a real
        (tmp SQLite) DB via `fresh_engine_for_db`, not a mocked query —
        the pipeline runner is stubbed only because running it is out of
        scope for an idempotency check, not to fake the dedup itself."""
        from fastapi.testclient import TestClient

        calls: List[str] = []

        def _counting_stub(
            doc_id: str,
            target_lang: str,
            segment_ids: Optional[List[str]] = None,
            *,
            org_id: str,
        ) -> None:
            calls.append(doc_id)

        monkeypatch.setattr(
            "app.api.v1.translations.run_pipeline_background", _counting_stub
        )
        from app.main import app

        client = TestClient(app)
        payload: Dict[str, object] = {
            "source_language": "en",
            "target_language": "fr",
            "request_id": "seam-conformance-c7-idempotency",
            "text_content": "Take 10mg daily.",
            "profile": {
                "archetype": "INFORMATIONAL",
                "tier": "TIER_C",
                "modality": "NARRATIVE",
            },
        }

        first = client.post("/api/v1/translations/", json=payload)
        second = client.post("/api/v1/translations/", json=payload)

        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        assert first.json()["job_id"] == second.json()["job_id"]
        assert len(calls) == 1, (
            "the second POST with the same request_id scheduled a second "
            "pipeline run — one request_id must produce one set of side "
            "effects"
        )


# ---------------------------------------------------------------------------
# C-9 — a locale below Qualified tier must be labelled as such (PENDING).
# ---------------------------------------------------------------------------


class TestC9LanguageTierPending:
    @covers("C-9")
    def test_language_tier_field_exists_and_defaults_none_pending_engine(
        self,
    ) -> None:
        """PENDING: no language-tier concept is implemented anywhere in the
        engine yet (TMX-LANG-TIERS is filed and READY, not built) — the only
        honest assertion available today is that the contract's escape
        hatch exists, is Optional, and defaults to None rather than to a
        fabricated tier label."""
        record = ProvenanceRecord()
        assert "language_tier" in type(record).model_fields
        assert record.language_tier is None


# ---------------------------------------------------------------------------
# C-1, C-3, C-6, C-8 — no live reSCApe pair available in this worktree.
#
# Bodies are written (not stubs) so intent is committed and mechanically
# visible, per this ticket's instruction. Each imports a client/service that
# does not exist yet; safe because `pytest.mark.skip` prevents execution.
# ---------------------------------------------------------------------------


@skip_covers(
    "C-1",
    reason=(
        "requires a live reSCApe pair (CROSS-REPO-PROTOCOL Rule 4 forbids "
        "mocking the counterpart); no HTTP client exists yet to call an "
        "unreachable engine through - blocked on TMX-SEAM-CLIENT (rewrite "
        "transmax_bridge.py as a thin HTTP client)."
    ),
)
def test_engine_unreachable_yields_typed_error_never_glossary_substitution() -> None:
    """C-1: with the TransMax engine unreachable, reSCApe's bridge client
    must surface a typed error and never fall back to glossary-deterministic
    substitution presented as a complete result — the exact defect ADR-0009
    exists to close (`transmax_bridge.py`'s six `return None` -> glossary
    fallback while still reporting `mode: "transmax_ai"`)."""
    from rescape_bridge_client import (  # type: ignore[import-not-found]
        TransMaxBridgeClient,
        TransMaxBridgeUnreachableError,
    )

    client = TransMaxBridgeClient(base_url="http://engine.invalid:0")
    with pytest.raises(TransMaxBridgeUnreachableError):
        client.translate(job_payload={"request_id": "seam-c1"})


@skip_covers(
    "C-3",
    reason=(
        "requires TMX-LANGDETECT-HOLD (READY, not yet built) - the typed "
        "hold this invariant asserts on does not exist in the engine yet."
    ),
)
def test_low_confidence_source_language_detection_yields_typed_hold() -> None:
    """C-3: a source document whose language cannot be confidently detected
    must return a typed hold, never a silent default to 'en'."""
    from app.services.language_detection import (  # type: ignore[import-not-found]
        detect_source_language,
    )

    result = detect_source_language("??? ambiguous mixed-script input ...")
    assert result.status == "HOLD_LOW_CONFIDENCE"
    assert result.detected_language != "en"


@skip_covers(
    "C-6",
    reason=(
        "requires a live reSCApe pair with resolvable signature_records "
        "(ADR-0009 clause 8); no TransMax-side wiring ticket has been filed "
        "yet for the lockability gate - blocked on TMX-SEAM-CLIENT plus that "
        "unfiled wiring ticket."
    ),
)
def test_submission_bound_segment_without_signature_ref_cannot_be_lockable() -> None:
    """C-6: a segment bound for submission cannot be marked lockable without
    a resolvable reference into reSCApe's `signature_records` — the gate
    lives in TransMax, the signature lives in reSCApe (ADR-0009 clause 8)."""
    from app.services.disposition_gate import (  # type: ignore[import-not-found]
        mark_lockable,
    )

    with pytest.raises(ValueError):
        mark_lockable(segment_id="s1", signature_ref=None, submission_bound=True)


@skip_covers(
    "C-8",
    reason=(
        "requires a live reSCApe pair (Rule 4 forbids mocking the "
        "counterpart) to independently re-verify chain_head_hash across the "
        "seam; the result block (AuditRef) is also not wired into any live "
        "route yet (TMX-SEAM-CONTRACT scope) - blocked on TMX-SEAM-CLIENT."
    ),
)
def test_every_result_carries_a_verifiable_chain_head_hash() -> None:
    """C-8: every result carries `audit.chain_head_hash` and a verify_url
    that independently re-verifies through the seam, not just a claim."""
    import httpx
    from rescape_bridge_client import (  # type: ignore[import-not-found]
        TransMaxBridgeClient,
    )

    client = TransMaxBridgeClient(base_url="http://engine.invalid:0")
    result = client.get_result(job_id="seam-c8")
    assert result.audit.chain_head_hash is not None
    verify_resp = httpx.get(result.audit.verify_url, timeout=5)
    assert verify_resp.status_code == 200
    assert verify_resp.json()["ok"] is True


# ---------------------------------------------------------------------------
# Meta suite — CRITICAL HONESTY RULE: this suite cannot report vacuous green.
# ---------------------------------------------------------------------------


class TestSeamSuiteHonesty:
    def test_all_nine_invariants_are_accounted_for_exactly_once(self) -> None:
        assert SKIPPED_INVARIANTS | COVERED_INVARIANTS == ALL_INVARIANTS
        assert SKIPPED_INVARIANTS.isdisjoint(COVERED_INVARIANTS)

    def test_every_covered_invariant_has_at_least_one_nonskipped_test(self) -> None:
        for invariant_id in sorted(COVERED_INVARIANTS):
            fns = INVARIANT_COVERAGE.get(invariant_id, [])
            assert fns, f"{invariant_id} is declared COVERED but has zero registered tests"
            for fn in fns:
                marks = list(getattr(fn, "pytestmark", []))
                assert not any(mark.name == "skip" for mark in marks), (
                    f"{fn.__qualname__} covers {invariant_id} but is "
                    "skip-marked - a skip-marked test cannot back a COVERED "
                    "invariant (this is exactly the vacuous-green failure "
                    "mode this meta-test exists to prevent)."
                )

    def test_pending_count_matches_the_declared_constant(self) -> None:
        assert len(PENDING_INVARIANTS) == DECLARED_PENDING_COUNT
        assert PENDING_INVARIANTS <= COVERED_INVARIANTS

    def test_every_skipped_invariant_carries_a_named_blocking_ticket(self) -> None:
        assert set(SKIP_COVERAGE) == SKIPPED_INVARIANTS
        for invariant_id, fns in SKIP_COVERAGE.items():
            assert fns, f"{invariant_id} is declared SKIPPED but has zero registered tests"
            for fn in fns:
                skip_marks = [
                    mark
                    for mark in getattr(fn, "pytestmark", [])
                    if mark.name == "skip"
                ]
                assert skip_marks, f"{fn.__qualname__} must carry pytest.mark.skip"
                reason = str(skip_marks[0].kwargs.get("reason", ""))
                assert "TMX-" in reason, (
                    f"{fn.__qualname__}'s skip reason must name a blocking "
                    f"ticket (got: {reason!r})"
                )

    def test_registered_invariants_match_the_declared_sets_exactly(self) -> None:
        """Catches drift: if a future edit adds/removes a test without
        updating the sets above, this fails instead of silently passing."""
        assert set(INVARIANT_COVERAGE) == COVERED_INVARIANTS
        assert set(SKIP_COVERAGE) == SKIPPED_INVARIANTS
