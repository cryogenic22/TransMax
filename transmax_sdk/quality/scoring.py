"""Confidence scoring for translation quality."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.telemetry.protocol import TelemetryProtocol


@dataclass
class ScoreResult:
    """Result of confidence scoring."""
    final_score: float
    band: str
    status: str
    components: Dict[str, float] = field(default_factory=dict)
    breakdown: List[str] = field(default_factory=list)


@dataclass
class ScoringWeights:
    """Configurable weights for confidence calculation."""
    penalty_defect_major: float = 15.0
    penalty_defect_minor: float = 5.0
    penalty_defect_critical: float = 100.0
    drift_threshold_medium: float = 0.05
    drift_threshold_high: float = 0.15
    penalty_drift_medium: float = 10.0
    penalty_drift_high: float = 25.0
    penalty_struct_formula: float = 10.0
    penalty_struct_dosage: float = 10.0
    penalty_struct_legal: float = 5.0
    penalty_struct_max_cap: float = 25.0
    penalty_process_no_reflexion: float = 5.0


class ConfidenceScorer:
    """TMX-CONF-02: Deterministic confidence scorer.

    Formula: Score = 100 - (Defects + Drift + Structure + Process)
    """

    def __init__(
        self,
        weights: Optional[ScoringWeights] = None,
        telemetry: Optional[TelemetryProtocol] = None,
    ) -> None:
        self._weights = weights or ScoringWeights()
        self._telemetry = telemetry or NoOpTelemetry()

    def calculate_score(
        self,
        defects: List[Dict[str, Any]],
        semantic_drift_score: float = 0.0,
        source_text: str = "",
        process_flags: Optional[Dict[str, bool]] = None,
    ) -> ScoreResult:
        process_flags = process_flags or {}
        w = self._weights
        breakdown = []
        components = {
            "base": 100.0,
            "deterministic_penalty": 0.0,
            "semantic_penalty": 0.0,
            "structural_penalty": 0.0,
            "process_penalty": 0.0,
        }

        major_count = sum(1 for d in defects if d.get("severity") == "MAJOR")
        minor_count = sum(1 for d in defects if d.get("severity") == "MINOR")
        critical_count = sum(1 for d in defects if d.get("severity") == "CRITICAL")

        # Hard rule: critical = blocked
        if critical_count > 0:
            breakdown.append(f"CRITICAL defect: Blocked (score -> 0)")
            return ScoreResult(
                final_score=0.0, band="Blocked", status="BLOCKED",
                components=components, breakdown=breakdown,
            )

        # Deterministic penalty
        det_penalty = major_count * w.penalty_defect_major + minor_count * w.penalty_defect_minor
        if det_penalty > 0:
            components["deterministic_penalty"] = det_penalty
            breakdown.append(f"Defects: -{det_penalty} ({major_count} major, {minor_count} minor)")

        # Semantic drift
        sem_penalty = 0.0
        if semantic_drift_score > w.drift_threshold_high:
            sem_penalty = w.penalty_drift_high
        elif semantic_drift_score > w.drift_threshold_medium:
            sem_penalty = w.penalty_drift_medium
        components["semantic_penalty"] = sem_penalty

        # Structural risk
        struct_penalty = 0.0
        if re.search(r'\b(\d+(\.\d+)?)\s*(mg|ml|g|mcg|mol|tablet|capsule)', source_text, re.IGNORECASE):
            struct_penalty += w.penalty_struct_dosage
        if re.search(r'\d+\s*[+\-*/=]\s*\d+', source_text):
            struct_penalty += w.penalty_struct_formula
        if re.search(r'\b(shall|must|prohibited|liable|obligation)\b', source_text, re.IGNORECASE):
            struct_penalty += w.penalty_struct_legal
        struct_penalty = min(struct_penalty, w.penalty_struct_max_cap)
        if struct_penalty > 0:
            components["structural_penalty"] = struct_penalty

        # Process risk
        proc_penalty = 0.0
        if not process_flags.get("reflexion_run", True):
            proc_penalty += w.penalty_process_no_reflexion
        if proc_penalty > 0:
            components["process_penalty"] = proc_penalty

        total_penalty = det_penalty + sem_penalty + struct_penalty + proc_penalty
        final_score = max(0.0, round(100.0 - total_penalty, 1))

        if final_score >= 95:
            band = "Very High"
        elif final_score >= 80:
            band = "High"
        elif final_score >= 60:
            band = "Medium"
        elif final_score > 0:
            band = "Low"
        else:
            band = "Blocked"

        status = "BLOCKED" if band == "Blocked" else "REVIEW_REQUIRED"

        return ScoreResult(
            final_score=final_score, band=band, status=status,
            components=components, breakdown=breakdown,
        )
