import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from app.core.scoring_config import SCORING_CONFIG

@dataclass
class ScoreResult:
    final_score: float
    band: str
    status: str
    components: Dict[str, float]
    breakdown_reasoning: List[str]

class ConfidenceService:
    """
    TMX-CONF-02: Deterministic Confidence Scorer.
    Implements the formula: Score = 100 - (Defects + Drift + Structure + Process)
    """
    
    @staticmethod
    def calculate_score(
        defects: List[Dict[str, Any]],
        semantic_drift_score: float = 0.0,
        source_text: str = "",
        process_flags: Dict[str, bool] = None
    ) -> ScoreResult:
        """
        Pure function calculation of confidence score.
        """
        process_flags = process_flags or {}
        config = SCORING_CONFIG
        
        breakdown = []
        components = {
            "base": 100.0,
            "deterministic_penalty": 0.0,
            "semantic_penalty": 0.0,
            "structural_penalty": 0.0,
            "process_penalty": 0.0
        }

        # 1. Deterministic Penalties (QA Defects)
        # ---------------------------------------
        major_count = sum(1 for d in defects if d.get('severity') == 'MAJOR')
        minor_count = sum(1 for d in defects if d.get('severity') == 'MINOR')
        critical_count = sum(1 for d in defects if d.get('severity') == 'CRITICAL')
        
        # Hard Rule: Critical = Blocked
        if critical_count > 0:
            breakdown.append(f"CRITICAL defect found: Blocked (Score -> 0)")
            return ScoreResult(
                final_score=0.0, 
                band="Blocked", 
                status="BLOCKED",
                components=components,
                breakdown_reasoning=breakdown
            )
            
        det_penalty = (major_count * config.penalty_defect_major) + \
                      (minor_count * config.penalty_defect_minor)
        
        if det_penalty > 0:
            components["deterministic_penalty"] = det_penalty
            breakdown.append(f"Defects: -{det_penalty} ({major_count} Major, {minor_count} Minor)")

        # 2. Semantic Risk (Drift)
        # ------------------------
        sem_penalty = 0.0
        if semantic_drift_score > config.drift_threshold_high:
            sem_penalty = config.penalty_drift_high
            breakdown.append(f"Semantic Drift High ({semantic_drift_score:.2f}): -{sem_penalty}")
        elif semantic_drift_score > config.drift_threshold_medium:
            sem_penalty = config.penalty_drift_medium
            breakdown.append(f"Semantic Drift Moderate ({semantic_drift_score:.2f}): -{sem_penalty}")
            
        components["semantic_penalty"] = sem_penalty

        # 3. Structural Risk (Regex Flags)
        # --------------------------------
        # We run regex checks on Source Text to identify risk categories
        struct_penalty = 0.0
        
        # Dosage? (mg, ml, tablet)
        if re.search(r'\b(\d+(\.\d+)?)\s*(mg|ml|g|mcg|mol|tablet|capsule)', source_text, re.IGNORECASE):
            struct_penalty += config.penalty_struct_dosage
            breakdown.append("Dosage/Units detected: High Risk")
            
        # Formula? (=, +, / with numbers)
        if re.search(r'\d+\s*[\+\-\*\/=]\s*\d+', source_text):
            struct_penalty += config.penalty_struct_formula
            breakdown.append("Mathematical formula detected: High Risk")
            
        # Legal? (shall, must, prohibited)
        if re.search(r'\b(shall|must|prohibited|liable|obligation)\b', source_text, re.IGNORECASE):
            struct_penalty += config.penalty_struct_legal
            breakdown.append("Legal obligation language detected")
            
        # Cap structural penalty
        if struct_penalty > config.penalty_struct_max_cap:
            struct_penalty = config.penalty_struct_max_cap
            
        if struct_penalty > 0:
            components["structural_penalty"] = struct_penalty
            breakdown.append(f"Structural Risk Adjustment: -{struct_penalty}")

        # 4. Process Risk
        # ---------------
        proc_penalty = 0.0
        if not process_flags.get("reflexion_run", True): # Default True for now
            proc_penalty += config.penalty_process_no_reflexion
            breakdown.append("Process skipped: Reflexion (Self-correction)")
            
        if proc_penalty > 0:
            components["process_penalty"] = proc_penalty

        # 5. Final Calculation
        # --------------------
        total_penalty = det_penalty + sem_penalty + struct_penalty + proc_penalty
        final_score = max(0.0, 100.0 - total_penalty)
        
        # Determine Band
        if final_score >= 95:
            band = "Very High"
            status = "REVIEW_REQUIRED" # Policy: Even high scores need review for Pharma
        elif final_score >= 80:
            band = "High"
            status = "REVIEW_REQUIRED"
        elif final_score >= 60:
            band = "Medium"
            status = "REVIEW_REQUIRED"
        elif final_score > 0:
            band = "Low"
            status = "REVIEW_REQUIRED"
        else:
            band = "Blocked"
            status = "BLOCKED"
            
        return ScoreResult(
            final_score=round(final_score, 1),
            band=band,
            status=status,
            components=components,
            breakdown_reasoning=breakdown
        )
