
from typing import Dict, Any, List, Optional
from app.core.defect_taxonomy import Defect, DefectCategory, DefectSeverity

class AnalyticalCheckService:
    """
    Enforces quality standards for the ANALYTICAL archetype.
    Focus: Psychometric Equivalence, Construct Stability, Sentiment Neutrality.
    """
    
    # Validated scale mappings (English -> Target)
    # In a real system, this would load from a database or config file
    ANCHOR_MAPPINGS = {
        "strongly agree": {
            "fr": ["tout à fait d'accord", "fortement d'accord"],
            "es": ["totalmente de acuerdo", "muy de acuerdo"],
            "ja": ["強くそう思う", "非常にそう思う"]
        },
        "agree": {
            "fr": ["d'accord"],
            "es": ["de acuerdo"],
            "ja": ["そう思う"]
        },
        "neutral": {
            "fr": ["neutre", "ni d'accord ni pas d'accord"],
            "es": ["neutral", "ni de acuerdo ni en desacuerdo"],
            "ja": ["どちらともいえない"]
        },
        "disagree": {
            "fr": ["pas d'accord"],
            "es": ["en desacuerdo"],
            "ja": ["そう思わない"]
        },
        "strongly disagree": {
            "fr": ["pas du tout d'accord", "fortement en désaccord"],
            "es": ["totalmente en desacuerdo", "muy en desacuerdo"],
            "ja": ["全くそう思わない"]
        }
    }
    
    # Negative polarity words for basic heuristic (Validation proof-of-concept)
    NEGATIVE_MARKERS = {
        "en": ["not", "never", "bad", "worst", "terrible", "fail"],
        "fr": ["pas", "jamais", "mauvais", "pire", "terrible", "échec"],
        "es": ["no", "nunca", "mal", "peor", "terrible", "fallo"],
        "ja": ["ない", "悪い", "最悪", "失敗"]
    }

    def check_anchors(self, source_text: str, target_text: str, target_lang: str) -> List[Defect]:
        """
        REQ-RES-01: Verifies that psychometric anchors are preserved.
        """
        defects = []
        source_lower = source_text.lower().strip()
        target_lower = target_text.lower().strip()
        
        # Check if source is a known anchor
        if source_lower in self.ANCHOR_MAPPINGS:
            valid_translations = self.ANCHOR_MAPPINGS[source_lower].get(target_lang, [])
            
            # If target language is supported and translation is not in valid list
            if valid_translations and target_lower not in valid_translations:
                defects.append(Defect(
                    category=DefectCategory.ANCHOR_MISMATCH,
                    severity=DefectSeverity.CRITICAL,
                    message=f"Psychometric Anchor Mismatch. Expected one of {valid_translations}, got '{target_lower}'.",
                    source_text=source_text,
                    suggestion=valid_translations[0]
                ))
                
        return defects

    def check_sentiment(self, source_text: str, target_text: str, target_lang: str) -> List[Defect]:
        """
        REQ-RES-02: Verifies sentiment stability (Heuristic).
        Checks if polarity flipped (e.g., positive source, negative target).
        """
        defects = []
        source_lower = source_text.lower()
        target_lower = target_text.lower()
        
        # Simple heuristic: Count negative markers
        source_neg_count = sum(1 for w in self.NEGATIVE_MARKERS.get("en", []) if w in source_lower)
        target_neg_count = sum(1 for w in self.NEGATIVE_MARKERS.get(target_lang, []) if w in target_lower)
        
        # If sign differs significantly (e.g. 0 vs 1+)
        # Note: This is a coarse filter for "Validation as Discipline" proof. 
        # Real impl would use TextBlob or transformers.
        if (source_neg_count == 0 and target_neg_count > 0) or (source_neg_count > 0 and target_neg_count == 0):
             # Exception: "agree" vs "not disagree" - but for analytical scales, double negatives are usually bad.
             defects.append(Defect(
                category=DefectCategory.SENTIMENT_SHIFT,
                severity=DefectSeverity.MAJOR,
                message=f"Potential Sentiment Shift detected (Polarity mismatch). Source Negatives: {source_neg_count}, Target Negatives: {target_neg_count}.",
                source_text=source_text
            ))
            
        return defects
