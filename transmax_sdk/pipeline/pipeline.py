"""Default translation pipeline: composable stages for headless SDK use."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from transmax_sdk.language.router import AnyToAnyRouter
from transmax_sdk.memory.glossary import GlossaryManager
from transmax_sdk.memory.tm import VectorTranslationMemory
from transmax_sdk.pipeline.state import PipelineState
from transmax_sdk.quality.gate import PharmaQualityGate
from transmax_sdk.quality.scoring import ConfidenceScorer
from transmax_sdk.telemetry.cost import CostTracker
from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.telemetry.protocol import TelemetryProtocol
from transmax_sdk.types import (
    QualityDefect,
    RoutePlan,
    RouteStrategy,
    SegmentResult,
    TranslationRequest,
    TranslationResult,
    TranslationStatus,
)


class DefaultTranslationPipeline:
    """Composable translation pipeline that works without a database.

    Stages: detect_lang -> check_tm -> translate -> quality_gate -> score -> build_result
    """

    def __init__(
        self,
        llm_provider=None,
        quality_gate: Optional[PharmaQualityGate] = None,
        tm: Optional[VectorTranslationMemory] = None,
        glossary: Optional[GlossaryManager] = None,
        router: Optional[AnyToAnyRouter] = None,
        scorer: Optional[ConfidenceScorer] = None,
        cost_tracker: Optional[CostTracker] = None,
        telemetry: Optional[TelemetryProtocol] = None,
        llm_providers: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._llm = llm_provider
        self._llm_providers = llm_providers or {}
        self._gate = quality_gate or PharmaQualityGate(telemetry=telemetry)
        self._tm = tm or VectorTranslationMemory(telemetry=telemetry)
        self._glossary = glossary or GlossaryManager(telemetry=telemetry)
        self._router = router or AnyToAnyRouter(telemetry=telemetry)
        self._scorer = scorer or ConfidenceScorer(telemetry=telemetry)
        self._cost_tracker = cost_tracker or CostTracker()
        self._telemetry = telemetry or NoOpTelemetry()

    async def execute(self, request: TranslationRequest) -> TranslationResult:
        """Execute the full pipeline."""
        with self._telemetry.span("pipeline.execute", {
            "source_lang": request.source_lang,
            "target_lang": request.target_lang,
            "segment_count": len(request.segments),
        }):
            state = PipelineState(
                segments=request.segments,
                source_lang=request.source_lang,
                target_lang=request.target_lang,
                domain=request.domain,
                glossary_id=request.glossary_id,
            )

            # Stage 1: Route planning
            route = self._router.plan_route(state.source_lang, state.target_lang)

            # Stage 2: TM lookup
            self._check_tm(state)

            # Stage 3: Translate (via LLM or mock)
            await self._translate(state, route)

            # Stage 4: Quality gates
            self._run_quality_gates(state)

            # Stage 5: Confidence scoring
            self._score(state)

            # Stage 6: Build result
            return self._build_result(state, route)

    def _check_tm(self, state: PipelineState) -> None:
        """Check TM for exact/fuzzy matches."""
        for seg in state.segments:
            match = self._tm.find_match(seg.source_text, state.source_lang, state.target_lang)
            if match and match["type"] == "exact":
                state.translations[seg.segment_id] = match["target"]
                state.translation_sources[seg.segment_id] = "TM_EXACT"
                state.confidence_scores[seg.segment_id] = 100.0

    def _resolve_provider(self, provider_name: Optional[str] = None):
        """Resolve LLM provider by name, falling back to default."""
        if provider_name and provider_name in self._llm_providers:
            return self._llm_providers[provider_name]
        return self._llm

    async def _translate(self, state: PipelineState, route: RouteStrategy) -> None:
        """Translate segments that don't have TM matches."""
        segments_to_translate = [
            s for s in state.segments if s.segment_id not in state.translations
        ]

        if not segments_to_translate:
            return

        if self._llm is None:
            # No LLM provider - use passthrough for headless testing
            for seg in segments_to_translate:
                state.translations[seg.segment_id] = f"[{state.target_lang}] {seg.source_text}"
                state.translation_sources[seg.segment_id] = "MT"
            return

        # Check if router supports smart routing with per-step providers
        if hasattr(self._router, "plan_smart_route") and self._llm_providers:
            smart_plan = self._router.plan_smart_route(
                state.source_lang, state.target_lang
            )
            await self._smart_translate(state, segments_to_translate, smart_plan)
            return

        # Fallback: standard routing
        if route == RouteStrategy.PIVOT_ENGLISH:
            await self._pivot_translate(state, segments_to_translate)
        else:
            await self._direct_translate(state, segments_to_translate)

    async def _direct_translate(self, state: PipelineState, segments) -> None:
        """Direct LLM translation."""
        segments_payload = [
            {"segment_id": s.segment_id, "source_text": s.source_text}
            for s in segments
        ]

        messages = [
            {"role": "system", "content": self._build_system_prompt(state)},
            {"role": "user", "content": json.dumps({
                "source_language": state.source_lang,
                "target_language": state.target_lang,
                "segments": segments_payload,
            })},
        ]

        result = await self._llm.complete(messages)
        self._parse_and_store(state, result["content"])

        if "usage" in result:
            usage = result["usage"]
            rec = self._cost_tracker.record(
                self._llm.name, result.get("model", "unknown"),
                usage.get("input_tokens", 0), usage.get("output_tokens", 0),
            )
            state.total_cost_usd += rec.cost_usd

    async def _pivot_translate(self, state: PipelineState, segments) -> None:
        """Two-step pivot translation: source -> en -> target."""
        # Step 1: source -> English
        segments_payload = [
            {"segment_id": s.segment_id, "source_text": s.source_text}
            for s in segments
        ]

        msg1 = [
            {"role": "system", "content": "Translate the following segments to English. Return JSON: {\"segments\": [{\"segment_id\": \"...\", \"target_text\": \"...\"}]}"},
            {"role": "user", "content": json.dumps({"segments": segments_payload})},
        ]
        r1 = await self._llm.complete(msg1)
        english_texts = self._parse_translations(r1["content"])

        # Step 2: English -> target
        en_segments = [
            {"segment_id": sid, "source_text": text}
            for sid, text in english_texts.items()
        ]

        msg2 = [
            {"role": "system", "content": self._build_system_prompt(state)},
            {"role": "user", "content": json.dumps({
                "source_language": "en",
                "target_language": state.target_lang,
                "segments": en_segments,
            })},
        ]
        r2 = await self._llm.complete(msg2)
        self._parse_and_store(state, r2["content"])

        # Track cost for both steps
        for r in [r1, r2]:
            if "usage" in r:
                u = r["usage"]
                rec = self._cost_tracker.record(
                    self._llm.name, r.get("model", "unknown"),
                    u.get("input_tokens", 0), u.get("output_tokens", 0),
                )
                state.total_cost_usd += rec.cost_usd

    async def _smart_translate(
        self, state: PipelineState, segments, smart_plan: RoutePlan
    ) -> None:
        """Translate using per-step provider assignments from SmartRouter."""
        if smart_plan.strategy == RouteStrategy.DIRECT:
            # Single step with specific provider
            step = smart_plan.steps[0] if smart_plan.steps else None
            provider = self._resolve_provider(
                step.provider_name if step else None
            )
            if provider is None:
                provider = self._llm
            await self._direct_translate_with_provider(state, segments, provider)
        else:
            # Pivot: step 0 = src->en, step 1 = en->tgt
            step0 = smart_plan.steps[0] if len(smart_plan.steps) > 0 else None
            step1 = smart_plan.steps[1] if len(smart_plan.steps) > 1 else None
            provider0 = self._resolve_provider(
                step0.provider_name if step0 else None
            ) or self._llm
            provider1 = self._resolve_provider(
                step1.provider_name if step1 else None
            ) or self._llm
            await self._pivot_translate_with_providers(
                state, segments, provider0, provider1
            )

    async def _direct_translate_with_provider(
        self, state: PipelineState, segments, provider
    ) -> None:
        """Direct translation using a specific provider."""
        segments_payload = [
            {"segment_id": s.segment_id, "source_text": s.source_text}
            for s in segments
        ]
        messages = [
            {"role": "system", "content": self._build_system_prompt(state)},
            {"role": "user", "content": json.dumps({
                "source_language": state.source_lang,
                "target_language": state.target_lang,
                "segments": segments_payload,
            })},
        ]
        result = await provider.complete(messages)
        self._parse_and_store(state, result["content"])
        if "usage" in result:
            usage = result["usage"]
            rec = self._cost_tracker.record(
                provider.name, result.get("model", "unknown"),
                usage.get("input_tokens", 0), usage.get("output_tokens", 0),
            )
            state.total_cost_usd += rec.cost_usd

    async def _pivot_translate_with_providers(
        self, state: PipelineState, segments, provider_step1, provider_step2
    ) -> None:
        """Pivot translation with potentially different providers per step."""
        # Step 1: source -> English
        segments_payload = [
            {"segment_id": s.segment_id, "source_text": s.source_text}
            for s in segments
        ]
        msg1 = [
            {"role": "system", "content": "Translate the following segments to English. Return JSON: {\"segments\": [{\"segment_id\": \"...\", \"target_text\": \"...\"}]}"},
            {"role": "user", "content": json.dumps({"segments": segments_payload})},
        ]
        r1 = await provider_step1.complete(msg1)
        english_texts = self._parse_translations(r1["content"])

        # Step 2: English -> target
        en_segments = [
            {"segment_id": sid, "source_text": text}
            for sid, text in english_texts.items()
        ]
        msg2 = [
            {"role": "system", "content": self._build_system_prompt(state)},
            {"role": "user", "content": json.dumps({
                "source_language": "en",
                "target_language": state.target_lang,
                "segments": en_segments,
            })},
        ]
        r2 = await provider_step2.complete(msg2)
        self._parse_and_store(state, r2["content"])

        for r, prov in [(r1, provider_step1), (r2, provider_step2)]:
            if "usage" in r:
                u = r["usage"]
                rec = self._cost_tracker.record(
                    prov.name, r.get("model", "unknown"),
                    u.get("input_tokens", 0), u.get("output_tokens", 0),
                )
                state.total_cost_usd += rec.cost_usd

    def _build_system_prompt(self, state: PipelineState) -> str:
        return (
            f"You are a pharmaceutical translation expert. "
            f"Translate from {state.source_lang} to {state.target_lang}. "
            f"Domain: {state.domain}. Preserve all numbers, units, and medical terminology exactly. "
            f"Return JSON: {{\"segments\": [{{\"segment_id\": \"...\", \"target_text\": \"...\"}}]}}"
        )

    def _parse_and_store(self, state: PipelineState, content: str) -> None:
        translations = self._parse_translations(content)
        for sid, text in translations.items():
            state.translations[sid] = text
            state.translation_sources[sid] = "MT"

    def _parse_translations(self, content: str) -> Dict[str, str]:
        """Parse LLM JSON response into segment_id -> text mapping."""
        try:
            data = json.loads(content)
            return {s["segment_id"]: s["target_text"] for s in data.get("segments", [])}
        except (json.JSONDecodeError, KeyError):
            return {}

    def _run_quality_gates(self, state: PipelineState) -> None:
        """Run quality checks on all translated segments."""
        constraints = state.constraint_pack or {}
        for seg in state.segments:
            translated = state.translations.get(seg.segment_id, "")
            if not translated:
                continue
            defects = self._gate.check_segment(
                source_text=seg.source_text,
                target_text=translated,
                source_lang=state.source_lang,
                target_lang=state.target_lang,
                constraints=constraints,
            )
            state.defects[seg.segment_id] = defects

    def _score(self, state: PipelineState) -> None:
        """Calculate confidence scores per segment."""
        for seg in state.segments:
            if seg.segment_id in state.confidence_scores:
                continue  # Already scored (TM exact)
            defects = state.defects.get(seg.segment_id, [])
            defect_dicts = [d.to_dict() for d in defects]
            result = self._scorer.calculate_score(
                defects=defect_dicts,
                source_text=seg.source_text,
                semantic_drift_score=state.drift_scores.get(seg.segment_id, 0.0),
            )
            state.confidence_scores[seg.segment_id] = result.final_score

    def _build_result(self, state: PipelineState, route: RouteStrategy) -> TranslationResult:
        """Build the final TranslationResult."""
        segment_results = []
        for seg in state.segments:
            segment_results.append(SegmentResult(
                segment_id=seg.segment_id,
                source_text=seg.source_text,
                translated_text=state.translations.get(seg.segment_id, ""),
                confidence=state.confidence_scores.get(seg.segment_id, 0.0),
                defects=state.defects.get(seg.segment_id, []),
                back_translation=state.back_translations.get(seg.segment_id),
                drift_score=state.drift_scores.get(seg.segment_id, 0.0),
                translation_source=state.translation_sources.get(seg.segment_id, "MT"),
                cost_usd=0.0,
            ))

        # Determine overall status
        all_defects = []
        for d_list in state.defects.values():
            all_defects.extend(d_list)
        verdict = self._gate.evaluate_verdict(all_defects)
        status = TranslationStatus(verdict["status"])

        return TranslationResult(
            segments=segment_results,
            source_lang=state.source_lang,
            target_lang=state.target_lang,
            route_strategy=route,
            status=status,
            audit_id=state.audit_id,
            total_cost_usd=state.total_cost_usd,
        )
