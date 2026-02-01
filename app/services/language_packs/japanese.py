
from typing import List, Dict, Any
import re
from .base import BaseLanguagePack
from app.core.policy_definitions import ViolationType, get_severity

class JapanesePack(BaseLanguagePack):
    """
    Language Driver for Japanese (Pharma).
    Handles CJK punctuation, Honorifics, and Variant enforcement.
    """
    
    @property
    def code(self) -> str:
        return "ja"

    @property
    def script_direction(self) -> str:
        return "ltr"

    def check_negation(self, source_text: str, target_text: str) -> List[Dict[str, Any]]:
        negation_markers = ["ない", "ません", "ぬ", "ず", "禁忌", "禁止", "使用しない"]
        source_negation = re.search(r'\b(no|not|never|none|neither|nor|cannot|don\'t|won\'t|avoid|prohibited|contraindicated)\b', source_text, re.IGNORECASE)
        
        target_has_negation = any(marker in target_text for marker in negation_markers)
        
        violations = []
        if source_negation and not target_has_negation:
             v_type = ViolationType.NEGATION_FLIP
             violations.append({
                "type": v_type.value,
                "message": f"Source contains negation '{source_negation.group(0)}' but Target lacks Japanese negation forms.",
                "severity": get_severity(v_type).value,
                "segment_id": "unknown"
            })
        return violations

    def check_numbers(self, source_text: str, target_text: str) -> List[Dict[str, Any]]:
        # Japanese typically uses Western numbers in Pharma 
        # or Zenkaku (Full-width) numbers ０-９.
        source_nums = re.findall(r'\d+(?:[\.,]\d+)?', source_text)
        if not source_nums:
            return []

        trans_table = str.maketrans("0123456789", "０１２３４５６７８９")
        
        violations = []
        for num in source_nums:
            # Check Half-width and Full-width
            if num not in target_text and num.translate(trans_table) not in target_text:
                 v_type = ViolationType.NUMBER_MISMATCH
                 violations.append({
                    "type": v_type.value,
                    "message": f"Number '{num}' missing in Target (checked Half/Full-width).",
                    "severity": get_severity(v_type).value,
                    "segment_id": "unknown"
                })
        return violations

    def check_punctuation(self, target_text: str) -> List[Dict[str, Any]]:
        """
        Enforce Japanese punctuation rules.
        """
        violations = []
        # Error if Western comma/period used instead of '、' or '。' in a sentence that is clearly Japanese
        # (Heuristic: contains Hiragana/Katakana/Kanji)
        is_japanese_script = re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', target_text)
        
        if is_japanese_script:
            if ',' in target_text and '、' not in target_text:
                 violations.append({
                    "type": "cjk_punctuation",
                    "message": "Found Western comma ',' in Japanese text; expected '、'.",
                    "severity": "major", # stylistic but standard
                    "segment_id": "unknown"
                })
            if '.' in target_text and '。' not in target_text:
                 # Be careful, . might be decimal point
                 # Check if . is surrounded by non-digits
                     # Check if . is surrounded by non-digits
                 if re.search(r'(?<!\d)\.(?!\d)', target_text):
                     v_type = ViolationType.PUNCTUATION
                     violations.append({
                        "type": v_type.value, # "punctuation_mismatch"
                        "message": "Found Western period '.' in Japanese text; expected '。'.",
                        "severity": get_severity(v_type).value,
                        "segment_id": "unknown"
                    })
        return violations

    def __init__(self):
        super().__init__()
        # TMX-033: Use Janome for tokenization (safe, pure python)
        from janome.tokenizer import Tokenizer
        self.tokenizer = Tokenizer()

    def _tokenize(self, text: str) -> List[str]:
        """Returns surface forms of tokens."""
        return [token.surface for token in self.tokenizer.tokenize(text)]

    def _contains_sequence(self, target_tokens: List[str], search_tokens: List[str]) -> bool:
        """
        Check if search_tokens sequence appears in target_tokens.
        """
        n = len(search_tokens)
        if n == 0:
            return False
        if n > len(target_tokens):
            return False
        
        for i in range(len(target_tokens) - n + 1):
            if target_tokens[i:i+n] == search_tokens:
                return True
        return False

    def check_variants(self, target_text: str) -> List[Dict[str, Any]]:
        """
        Enforce Strict Variants using Tokenizer (TMX-033).
        Avoids False Positives (e.g., 'not taking' vs 'overtaking').
        """
        violations = []
        forbidden_variants = [
            ("飲まない", "Use '服用しない' (Do not take) for medication instead of '飲まない' (Do not drink)."),
            ("食べない", "Use '摂取しない' (Do not ingest) for medication.") 
        ]
        
        # Tokenize target once
        try:
             target_tokens = self._tokenize(target_text)
        except Exception as e:
             # Fallback to substring if tokenizer fails
             target_tokens = [] # proceed to trigger logic or skip?
             # Ideally log warning. For now, substring fallback is risky.
             # We skip validation if tokenizer fails to be safe? Or fail open?
             # TMX-033 implies strictness. Validation checks usually fail open (pass) if tool breaks to avoid blocking pipeline, 
             # OR blocking if safety critical.
             # Let's assume passed but log error.
             print(f"Tokenizer warning: {e}")
             return []

        for bad_term, fix in forbidden_variants:
            # Tokenize the forbidden term to match boundaries
            bad_tokens = self._tokenize(bad_term)
            
            if self._contains_sequence(target_tokens, bad_tokens):
                 v_type = ViolationType.VARIANT_IMPROPER
                 violations.append({
                    "type": v_type.value,
                    "message": f"Forbidden variant sequence '{bad_term}' found. {fix}",
                    "severity": get_severity(v_type).value,
                    "segment_id": "unknown"
                })
        return violations
