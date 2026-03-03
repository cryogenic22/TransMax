from pydantic import BaseModel, ConfigDict, Field

class ScoringWeights(BaseModel):
    """
    TMX-CONF-01: Admin-tunable weights for the Confidence Scorer.
    Allows adjusting penalties without changing code logic.
    """
    # Deterministic Penalties
    penalty_defect_major: float = Field(15.0, description="Points deducted for each MAJOR defect")
    penalty_defect_minor: float = Field(5.0, description="Points deducted for each MINOR defect")
    penalty_defect_critical: float = Field(100.0, description="Points deducted for CRITICAL (Hard Block)")
    
    # Semantic Risk (Drift)
    # Thresholds
    drift_threshold_medium: float = Field(0.05, description="Drift score above this triggers generic penalty")
    drift_threshold_high: float = Field(0.15, description="Drift score above this triggers high penalty")
    
    # Penalties
    penalty_drift_medium: float = Field(10.0, description="Penalty for moderate drift (0.05 - 0.15)")
    penalty_drift_high: float = Field(25.0, description="Penalty for high drift (> 0.15)")
    
    # Structural Risk (High-stakes content types)
    penalty_struct_formula: float = Field(10.0, description="Contains mathematical formulas")
    penalty_struct_dosage: float = Field(10.0, description="Contains dosage instructions")
    penalty_struct_legal: float = Field(5.0, description="Contains legal obligations (must/shall)")
    penalty_struct_max_cap: float = Field(25.0, description="Maximum total structural penalty")
    
    # Process Risk
    penalty_process_no_reflexion: float = Field(5.0, description="Skipped self-correction step")
    penalty_process_no_audit: float = Field(10.0, description="Audit log incomplete")

    model_config = ConfigDict(frozen=True)

# Default instance (Singleton-ish)
SCORING_CONFIG = ScoringWeights()
