"""
Deep Language Pack for Portuguese (pt / pt-br / pt-pt).
Handles European vs Brazilian variants, decimal formatting, negation.
"""
from typing import List, Dict, Any
import re
from .base import BaseLanguagePack
from app.core.policy_definitions import ViolationType, get_severity


class PortuguesePack(BaseLanguagePack):
    """
    Language Driver for Portuguese (Pharma).
    Supports pt-BR (Brazilian) and pt-PT (European) variants.
    """

    def __init__(self, variant: str = "brazilian"):
        super().__init__()
        self._variant = variant  # "brazilian" or "european"

    @property
    def code(self) -> str:
        return "pt-br" if self._variant == "brazilian" else "pt-pt"

    @property
    def script_direction(self) -> str:
        return "ltr"

    @property
    def prompt_instruction(self) -> str:
        if self._variant == "european":
            return (
                "ENSURE HIGH RIGOR: Use formal European Portuguese (pt-PT) suitable for "
                "pharmaceutical and medical documents. Follow EMA (European Medicines Agency) "
                "terminology standards. Use the European Portuguese spelling convention."
            )
        return (
            "ENSURE HIGH RIGOR: Use formal Brazilian Portuguese (pt-BR) suitable for "
            "pharmaceutical and medical documents. Follow ANVISA terminology standards. "
            "Use the Brazilian Portuguese spelling convention per the 2009 Orthographic Agreement."
        )

    def check_negation(self, source_text: str, target_text: str) -> List[Dict[str, Any]]:
        """Check negation preservation for Portuguese."""
        negation_markers = [
            "não", "nunca", "jamais", "nenhum", "nenhuma", "nem", "nada",
            "ninguém", "proibido", "contraindicado", "evitar",
        ]
        source_negation = re.search(
            r'\b(no|not|never|none|neither|nor|cannot|don\'t|won\'t|avoid|prohibited|contraindicated|do not)\b',
            source_text, re.IGNORECASE
        )

        target_lower = target_text.lower()
        target_has_negation = any(marker in target_lower for marker in negation_markers)

        violations = []
        if source_negation and not target_has_negation:
            v_type = ViolationType.NEGATION_FLIP
            violations.append({
                "type": v_type.value,
                "message": f"Source contains negation '{source_negation.group(0)}' but target lacks Portuguese negation markers.",
                "severity": get_severity(v_type).value,
                "segment_id": "unknown",
            })
        return violations

    def check_numbers(self, source_text: str, target_text: str) -> List[Dict[str, Any]]:
        """
        Portuguese uses comma for decimal separator (1.5 → 1,5)
        and period/space for thousands (1,000 → 1.000 or 1 000).
        Word-bounded numeric check (TMX-3410).
        """
        violations = []
        for num in self._find_missing_numbers(source_text, target_text, accept_decimal_swap=True):
            v_type = ViolationType.NUMBER_MISMATCH
            violations.append({
                "type": v_type.value,
                "message": f"Number '{num}' missing in Portuguese target (checked both '.' and ',' decimal).",
                "severity": get_severity(v_type).value,
                "segment_id": "unknown",
            })
        return violations

    def check_punctuation(self, target_text: str) -> List[Dict[str, Any]]:
        """Portuguese uses standard Western punctuation."""
        return []

    def check_variants(self, target_text: str) -> List[Dict[str, Any]]:
        """
        Check for variant consistency (Brazilian vs European).
        Common pharma term differences.
        """
        violations = []
        if self._variant == "brazilian":
            # European terms that should be Brazilian
            eu_to_br = [
                ("medicamento", None),  # same in both — no check needed
                ("doente", "paciente"),  # EU "doente" → BR "paciente"
            ]
            for eu_term, br_term in eu_to_br:
                if br_term and eu_term in target_text.lower() and br_term not in target_text.lower():
                    violations.append({
                        "type": "variant_mismatch",
                        "message": f"European Portuguese term '{eu_term}' detected; use Brazilian '{br_term}'.",
                        "severity": "minor",
                        "segment_id": "unknown",
                    })
        return violations

    def extract_frequency(self, text: str) -> List[Dict[str, Any]]:
        """Extract dosing frequency from Portuguese text."""
        text_lower = text.lower()
        freqs = []
        if "uma vez ao dia" in text_lower or "uma vez por dia" in text_lower:
            freqs.append({"count": 1.0, "interval": "day", "raw": "uma vez ao dia"})
        if "duas vezes ao dia" in text_lower or "duas vezes por dia" in text_lower:
            freqs.append({"count": 2.0, "interval": "day", "raw": "duas vezes ao dia"})
        if "três vezes ao dia" in text_lower or "três vezes por dia" in text_lower:
            freqs.append({"count": 3.0, "interval": "day", "raw": "três vezes ao dia"})
        return freqs
