
from typing import List, Dict, Any
import re
from .base import BaseLanguagePack
from app.core.policy_definitions import ViolationType, get_severity

class SpanishPack(BaseLanguagePack):
    @property
    def code(self) -> str:
        return "es"

    @property
    def script_direction(self) -> str:
        return "ltr"

    def check_negation(self, source_text: str, target_text: str) -> List[Dict[str, Any]]:
        source_negation = re.search(r'\b(no|not|never|none|neither|nor|cannot|don\'t|won\'t)\b', source_text, re.IGNORECASE)
        
        negation_markers = ["no", "nunca", "jamás", "tampoco", "nadie", "nada", "ningún"]
        target_has_negation = any(marker in target_text.lower() for marker in negation_markers)

        violations = []
        if source_negation and not target_has_negation:
             v_type = ViolationType.NEGATION_FLIP
             violations.append({
                "type": v_type.value,
                "message": f"Source contains negation '{source_negation.group(0)}' but Target lacks Spanish negation markers.",
                "severity": get_severity(v_type).value,
                "segment_id": "unknown"
            })
        return violations

    def check_numbers(self, source: str, target: str) -> List[Dict[str, Any]]:
        # Word-bounded match: substring `in` would treat "10" as present in "100 mg"
        # and silently miss order-of-magnitude tampering (TMX-3408 / eval number_001).
        # Accept both `.` and `,` decimal separators per Spanish convention.
        vocab = re.findall(r'\b\d+(?:[\.,]\d+)?\b', source)
        violations = []
        for num in vocab:
            forms = {num}
            if '.' in num:
                forms.add(num.replace('.', ','))
            if ',' in num:
                forms.add(num.replace(',', '.'))
            found = any(
                re.search(rf'\b{re.escape(form)}\b', target) for form in forms
            )
            if not found:
                v_type = ViolationType.NUMBER_MISMATCH
                violations.append({
                    "type": v_type.value,
                    "message": f"Missing number {num}",
                    "severity": get_severity(v_type).value
                })
        return violations

    def check_punctuation(self, target_text: str) -> List[Dict[str, Any]]:
        # Check inverted question/exclamation marks?
        # Only if strict. For now, empty.
        return []
        
    def check_variants(self, t): return []
