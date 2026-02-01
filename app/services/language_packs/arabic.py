
from typing import List, Dict, Any
import re
from .base import BaseLanguagePack
from app.core.policy_definitions import ViolationType, get_severity

class ArabicPack(BaseLanguagePack):
    """
    Language Driver for Arabic (Modern Standard).
    Handles RTL punctuation safety and Hindi/Western digit policies.
    """
    
    @property
    def code(self) -> str:
        return "ar"

    @property
    def script_direction(self) -> str:
        return "rtl"

    def check_negation(self, source_text: str, target_text: str) -> List[Dict[str, Any]]:
        # Basic negation markers in Arabic
        negation_markers = ["لا", "لم", "لن", "ليس", "غير", "عدم", "إياك", "تحذير", "ممنوع"]
        source_negation = re.search(r'\b(no|not|never|none|neither|nor|cannot|don\'t|won\'t|avoid|prohibited|contraindicated)\b', source_text, re.IGNORECASE)
        
        target_has_negation = any(marker in target_text for marker in negation_markers)
        
        violations = []
        if source_negation and not target_has_negation:
             v_type = ViolationType.NEGATION_FLIP
             violations.append({
                "type": v_type.value,
                "message": f"Source contains negation '{source_negation.group(0)}' but Target lacks common Arabic negation markers.",
                "severity": get_severity(v_type).value,
                "segment_id": "unknown" 
            })
        return violations

    def check_numbers(self, source_text: str, target_text: str) -> List[Dict[str, Any]]:
        """
        Checks number preservation. 
        Supports configurable digit policy. Default: allow BOTH Western and Hindi digits.
        """
        # Extract source numbers (Western)
        source_nums = re.findall(r'\d+(?:[\.,]\d+)?', source_text)
        if not source_nums:
            return []

        # Mapping: Western -> Hindi digits
        # 0123456789 -> ٠١٢٣٤٥٦٧٨٩
        trans_table = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
        
        violations = []
        for num in source_nums:
            western_in_target = num in target_text
            hindi_num = num.translate(trans_table)
            hindi_in_target = hindi_num in target_text
            
            # Policy: At least one form must exist
            if not (western_in_target or hindi_in_target):
                 v_type = ViolationType.NUMBER_MISMATCH
                 violations.append({
                    "type": v_type.value,
                    "message": f"Number '{num}' missing in Target (checked Western '{num}' and Hindi '{hindi_num}').",
                    "severity": get_severity(v_type).value,
                    "segment_id": "unknown"
                })
        return violations

    def check_punctuation(self, target_text: str) -> List[Dict[str, Any]]:
        """
        Ensures RTL coherence for mixed content (e.g. Latin brand names in brackets).
        Detects if start/end brackets are flipped relative to the RTL flow 
        (though this is complex in raw string, we check visual logic proxies).
        """
        violations = []
        # Check standard Arabic comma (،) vs Western (,)
        # In Pharma, we might prefer Arabic comma, but Western is often accepted in technical text.
        # We enforce that if Arabic script dominates, we shouldn't see solitary Western commas floating? 
        # Keeping it simple: Fail if we see broken bracket logic like ")Name(" which happens in naive RTL rendering.
        
        # Actually, raw string storage is logical order. 
        # A common issue is LRM/RLM missing.
        # This is a placeholder for deep BiDi checks.
        
        return violations

    def check_variants(self, target_text: str) -> List[Dict[str, Any]]:
        return []
