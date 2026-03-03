"""
Language-pair confidence calibration.

Different language pairs have inherently different difficulty levels.
This module provides pair-specific scoring adjustments so that
a 90% score for en→ja means the same quality bar as 90% for en→fr.

Used by ConfidenceService to adjust scoring per language pair.
"""
from dataclasses import dataclass
from typing import Dict, Tuple, Optional


@dataclass(frozen=True)
class PairCalibration:
    """Calibration profile for a source→target language pair."""
    # Multiplier applied to defect penalties (>1 = more lenient, <1 = stricter)
    defect_multiplier: float = 1.0
    # Additional structural penalty for inherently hard pairs
    pair_difficulty_penalty: float = 0.0
    # Drift threshold adjustments (some pairs naturally drift more)
    drift_threshold_medium: Optional[float] = None
    drift_threshold_high: Optional[float] = None
    # Minimum confidence floor (never report higher than deserved)
    confidence_floor: float = 0.0
    # Human review always required (regardless of score)
    always_review: bool = True  # Default for pharma


# Language pair calibration table
# Key: (source, target) or ("*", target) for any-to-target
PAIR_CALIBRATIONS: Dict[Tuple[str, str], PairCalibration] = {
    # === Easy pairs (structurally similar languages) ===
    ("en", "fr"): PairCalibration(defect_multiplier=1.0),
    ("en", "es"): PairCalibration(defect_multiplier=1.0),
    ("en", "de"): PairCalibration(defect_multiplier=1.0, pair_difficulty_penalty=2.0),
    ("en", "it"): PairCalibration(defect_multiplier=1.0),
    ("en", "pt"): PairCalibration(defect_multiplier=1.0),
    ("en", "pt-br"): PairCalibration(defect_multiplier=1.0),
    ("en", "nl"): PairCalibration(defect_multiplier=1.0),
    ("en", "sv"): PairCalibration(defect_multiplier=1.0),
    ("en", "da"): PairCalibration(defect_multiplier=1.0),
    ("en", "no"): PairCalibration(defect_multiplier=1.0),

    # === Medium pairs (different grammar/structure) ===
    ("en", "ru"): PairCalibration(defect_multiplier=0.9, pair_difficulty_penalty=3.0),
    ("en", "pl"): PairCalibration(defect_multiplier=0.9, pair_difficulty_penalty=3.0),
    ("en", "cs"): PairCalibration(defect_multiplier=0.9, pair_difficulty_penalty=3.0),
    ("en", "tr"): PairCalibration(defect_multiplier=0.9, pair_difficulty_penalty=3.0),
    ("en", "el"): PairCalibration(defect_multiplier=0.9, pair_difficulty_penalty=3.0),
    ("en", "hu"): PairCalibration(defect_multiplier=0.85, pair_difficulty_penalty=4.0),
    ("en", "fi"): PairCalibration(defect_multiplier=0.85, pair_difficulty_penalty=4.0),

    # === Hard pairs (different script, word order, morphology) ===
    ("en", "ja"): PairCalibration(
        defect_multiplier=0.8, pair_difficulty_penalty=5.0,
        drift_threshold_medium=0.08, drift_threshold_high=0.20,
    ),
    ("en", "zh"): PairCalibration(
        defect_multiplier=0.8, pair_difficulty_penalty=5.0,
        drift_threshold_medium=0.08, drift_threshold_high=0.20,
    ),
    ("en", "zh-cn"): PairCalibration(
        defect_multiplier=0.8, pair_difficulty_penalty=5.0,
        drift_threshold_medium=0.08, drift_threshold_high=0.20,
    ),
    ("en", "zh-tw"): PairCalibration(
        defect_multiplier=0.8, pair_difficulty_penalty=5.0,
        drift_threshold_medium=0.08, drift_threshold_high=0.20,
    ),
    ("en", "ko"): PairCalibration(
        defect_multiplier=0.8, pair_difficulty_penalty=5.0,
        drift_threshold_medium=0.08, drift_threshold_high=0.20,
    ),
    ("en", "ar"): PairCalibration(
        defect_multiplier=0.8, pair_difficulty_penalty=5.0,
        drift_threshold_medium=0.08, drift_threshold_high=0.20,
    ),
    ("en", "he"): PairCalibration(
        defect_multiplier=0.8, pair_difficulty_penalty=5.0,
        drift_threshold_medium=0.08, drift_threshold_high=0.20,
    ),
    ("en", "hi"): PairCalibration(
        defect_multiplier=0.85, pair_difficulty_penalty=4.0,
        drift_threshold_medium=0.07, drift_threshold_high=0.18,
    ),
    ("en", "th"): PairCalibration(
        defect_multiplier=0.85, pair_difficulty_penalty=4.0,
    ),
    ("en", "vi"): PairCalibration(
        defect_multiplier=0.9, pair_difficulty_penalty=3.0,
    ),
}


def get_pair_calibration(source: str, target: str) -> PairCalibration:
    """
    Get the calibration profile for a language pair.
    Falls back to wildcard (*→target), then to defaults.
    """
    source = source.lower()
    target = target.lower()

    # Exact match
    if (source, target) in PAIR_CALIBRATIONS:
        return PAIR_CALIBRATIONS[(source, target)]

    # Wildcard source
    if ("*", target) in PAIR_CALIBRATIONS:
        return PAIR_CALIBRATIONS[("*", target)]

    # Default — no adjustment
    return PairCalibration()
