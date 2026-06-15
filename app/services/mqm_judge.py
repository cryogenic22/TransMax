"""
Independent MQM judge (TMX-MQM-4).

The judge is the platform's independent assessor: it produces span-level MQM
annotations (§5.7) over a translation and is structurally incapable of doing
anything else — it cannot rewrite, and it cannot set pass status (the pure MQM
engine, fed these annotations, decides). Separation of authorship (§6.2) is
enforced by the contract: the judge is given SOURCE + TARGET + grounding only,
never the translator's reasoning.

Model-agnostic per the programme decision (ADR-0007): the judge runs on
`get_llm(task="judge")`. With the router off it resolves to the default model
(the "single in-boundary model + compensating controls" default); when a second
independent in-boundary model is validated, routing flips it to a different
lineage with no code change here.

`parse_judge_response` is the pure, deterministic core (no LLM) and carries the
tests; `judge_segments` is the thin async LLM wrapper.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Sequence

from app.agents.prompts.registry import PromptRegistry
from app.core.defect_taxonomy import DefectSeverity, MqmDimension
from app.core.mqm_annotation import MqmAnnotation, Span
from app.services.json_parser import RobustParser

logger = logging.getLogger(__name__)


def _coerce_dimension(value: Any) -> Optional[MqmDimension]:
    if not value:
        return None
    s = str(value).strip().lower()
    for d in MqmDimension:
        if d.value.lower() == s or d.name.lower() == s:
            return d
    return None  # unknown dimension → skip; never guess (A3)


def _coerce_severity(value: Any) -> Optional[DefectSeverity]:
    if not value:
        return None
    s = str(value).strip().upper()
    for sev in DefectSeverity:
        if sev.value == s:
            return sev
    return None


def parse_judge_response(
    raw: str,
    *,
    judge_id: str,
    prompt_version: str,
    model_version: Optional[str] = None,
) -> List[MqmAnnotation]:
    """Parse a judge LLM response into MQM annotations. Pure + tolerant:
    malformed entries (unknown dimension/severity) are skipped, never guessed."""
    try:
        data: Dict[str, Any] = RobustParser.parse(raw) or {}
    except Exception as e:
        logger.warning("judge response parse failed: %s", e)
        return []

    out: List[MqmAnnotation] = []
    for item in (data.get("annotations") or []):
        if not isinstance(item, dict):
            continue
        dim = _coerce_dimension(item.get("dimension"))
        sev = _coerce_severity(item.get("severity"))
        if dim is None or sev is None:
            continue
        src = item.get("source_span")
        tgt = item.get("target_span")
        evidence = item.get("evidence_refs")
        out.append(MqmAnnotation(
            segment_id=item.get("segment_id"),
            dimension=dim,
            subtype=item.get("subtype"),
            severity=sev,
            explanation=str(item.get("explanation", "")),
            rule_ref=item.get("rule_ref"),
            evidence_refs=list(evidence) if isinstance(evidence, list) else [],
            suggested_fix=item.get("suggested_fix"),
            source_span=Span(text=str(src)) if src else None,
            target_span=Span(text=str(tgt)) if tgt else None,
            produced_by="critique-agent",
            judge_id=judge_id,
            prompt_version=prompt_version,
            model_version=model_version,
        ))
    return out


async def judge_segments(
    segments: Sequence[Dict[str, Any]],
    source_language: str,
    target_language: str,
    *,
    content_type: str = "",
    grounding: Optional[Dict[str, Any]] = None,
    judge_id: str = "judge-a",
    version: str = "latest",
) -> List[MqmAnnotation]:
    """Run the independent judge over translated segments → MQM annotations.

    Given SOURCE + TARGET + grounding only (never the translator's reasoning).
    Returns [] if nothing is translated yet.
    """
    seg_payload = [
        {
            "segment_id": s.get("segment_id") or s.get("id"),
            "source": s.get("source_text"),
            "target": s.get("translated_text"),
        }
        for s in segments
        if s.get("translated_text")
    ]
    if not seg_payload:
        return []

    prompt = PromptRegistry.load("judge", version)
    user = (
        prompt.user
        .replace("{{source_language}}", source_language)
        .replace("{{target_language}}", target_language)
        .replace("{{content_type}}", content_type or "")
        .replace("{{grounding_json}}", json.dumps(grounding or {}, ensure_ascii=False))
        .replace("{{segments_json}}", json.dumps(seg_payload, ensure_ascii=False))
    )

    from langchain_core.messages import HumanMessage, SystemMessage

    from app.services.llm import get_llm, resolve_model

    llm = get_llm(task="judge")  # model-agnostic; router off ⇒ default model
    resp = await llm.ainvoke([SystemMessage(content=prompt.system), HumanMessage(content=user)])
    raw = resp.content if isinstance(resp.content, str) else str(resp.content)

    return parse_judge_response(
        raw,
        judge_id=judge_id,
        prompt_version=f"judge@{prompt.version}",
        # Record the REAL resolved model (A6) — identical to the default until
        # `enable_llm_router` maps task="judge" to a 2nd lineage, at which point
        # an ensemble's per-judge provenance must not lie.
        model_version=resolve_model(task="judge"),
    )
