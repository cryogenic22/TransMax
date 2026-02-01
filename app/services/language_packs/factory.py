from .base import BaseLanguagePack
from .arabic import ArabicPack
from .japanese import JapanesePack
from .french import FrenchPack
from .german import GermanPack
from .spanish import SpanishPack

import re
from typing import List, Dict, Any
from app.core.policy_definitions import ViolationType, get_severity

class GenericLanguagePack(BaseLanguagePack):
    def __init__(self, instruction: str = ""):
        self._instruction = instruction

    @property
    def prompt_instruction(self) -> str:
        return self._instruction


# ... (rest of class unchanged, skipping it in replacement if possible, but replace_file_content works on chunks)
# I will replace the imports at the top first.

# Actually I can do two replacements or one big one if they are close.
# Imports are at line 1.
# _packs dict is at line 136.
# They are far apart. I should use multi_replace or two calls.
# I will use multi_replace.
    @property
    def code(self): return "en"
    @property
    def script_direction(self): return "ltr"
    def check_negation(self, source_text: str, target_text: str) -> List[Dict[str, Any]]:
        # Basic keyword mapping for Indo-European defaults (En/Fr)
        negators = {
            "en": ["not", "no", "don't", "cannot", "never"],
            "fr": ["pas", "aucun", "ne", "non", "jamais"]
        }
        
        source_lower = source_text.lower()
        target_lower = target_text.lower()
        
        # Heuristic check
        source_has_neg = any(f" {w} " in f" {source_lower} " for w in negators['en'])
        target_has_neg = any(f" {w} " in f" {target_lower} " for w in negators.get('fr', []) + negators['en'])
        
        violations = []
        if source_has_neg and not target_has_neg:
             v_type = ViolationType.NEGATION_FLIP
             violations.append({
                "type": v_type.value,
                "severity": get_severity(v_type).value,
                "message": "Potential negation found in source but missing in target (Default Pack).",
                "segment_id": "unknown"
            })
        return violations

    def check_numbers(self, source: str, target: str) -> List[Dict[str, Any]]: 
         # Basic Western number check
         vocab = re.findall(r'\b\d+(?:[\.,]\d+)?\b', source)
         violations = []
         for num in vocab:
             if num not in target:
                 v_type = ViolationType.NUMBER_MISMATCH
                 violations.append({
                     "type": v_type.value, 
                     "message": f"Missing number {num} (Default)", 
                     "severity": get_severity(v_type).value
                 })
         return violations
    def check_punctuation(self, t): return []
    def check_variants(self, t): return []

    def check_placeholders(self, source: str, target: str) -> List[Dict[str, Any]]:
        """
        TMX-034: Enforce strict placeholder preservation.
        Matches {{...}} and [#].
        """
        from collections import Counter
        # Regex for {{variable}} and [1]
        pattern = r'(\{\{.*?\}\}|\[\d+\])'
        
        source_phs = re.findall(pattern, source)
        if not source_phs:
            return []
            
        target_phs = re.findall(pattern, target)
        
        # Multiset comparison
        s_count = Counter(source_phs)
        t_count = Counter(target_phs)
        
        violations = []
        
        # Check for dropped or corrupted placeholders
        diff = s_count - t_count
        if diff:
            missing = list(diff.elements())
            v_type = ViolationType.PLACEHOLDER_CORRUPTION
            
            violations.append({
                "type": v_type.value,
                "message": f"Placeholders missing or corrupted: {missing}",
                "severity": get_severity(v_type).value,
                "segment_id": "unknown"
            })
            
        # Check for hallucinated placeholders
        diff_added = t_count - s_count
        if diff_added:
             added = list(diff_added.elements())
             v_type = ViolationType.PLACEHOLDER_CORRUPTION # Same type? Or HALLUCINATION? 
             # TMX-034 focuses on Integrity. Added is also integrity fail.
             
             violations.append({
                "type": v_type.value,
                "message": f"Placeholders hallucinated: {added}",
                "severity": get_severity(v_type).value,
                "segment_id": "unknown"
             })
             
        return violations

    def extract_frequency(self, text: str) -> List[Dict[str, Any]]:
        """
        TMX-031: Basic Extraction for En/Fr/Latin Sig.
        Normalization: (per_day_count).
        """
        text_lower = text.lower()
        freqs = []
        
        # Latin Abbrevs (Word Boundary)
        latin_map = {
            "bid": 2.0, "tid": 3.0, "qid": 4.0, "qd": 1.0, "q.d.": 1.0, "b.i.d.": 2.0
        }
        for k, v in latin_map.items():
            if re.search(r'\b' + re.escape(k) + r'\b', text_lower):
                 freqs.append({"count": v, "interval": "day", "raw": k})
                 
        # English Phrases
        if "once daily" in text_lower or "1 time daily" in text_lower:
            freqs.append({"count": 1.0, "interval": "day", "raw": "once daily"})
        if "twice daily" in text_lower or "2 times daily" in text_lower:
            freqs.append({"count": 2.0, "interval": "day", "raw": "twice daily"})
            
        # French Phrases
        if "une fois par jour" in text_lower:
             freqs.append({"count": 1.0, "interval": "day", "raw": "une fois par jour"})
        if "deux fois par jour" in text_lower:
             freqs.append({"count": 2.0, "interval": "day", "raw": "deux fois par jour"})
             
        return freqs

class LanguagePackFactory:
    _packs = {
        # Tier 1: Deep Quality Packs
        "ar": ArabicPack(),
        "ja": JapanesePack(),
        "fr": FrenchPack(),
        "de": GermanPack(),
        "es": SpanishPack(),
        
        # Tier 1 Variants & Extended
        "fr-ca": GenericLanguagePack("Use Canadian French (fr-CA) terminology and conventions."),
        "zh-tw": GenericLanguagePack("ENSURE HIGH RIGOR: Use formal Traditional Chinese (zh-TW) suitable for professional/medical contexts in Taiwan."),
        
        # Tier 1 (Pending Deep Pack -> Uses Generic for now)
        "en": GenericLanguagePack(),
        "zh": GenericLanguagePack("ENSURE HIGH RIGOR: Use formal Simplified Chinese (zh-CN) for professional/medical contexts."),
        "zh-cn": GenericLanguagePack("ENSURE HIGH RIGOR: Use formal Simplified Chinese (zh-CN) for professional/medical contexts."),
        "pt": GenericLanguagePack(),
        "ru": GenericLanguagePack(),
        "it": GenericLanguagePack(),
        
        # Tier 2: Generic Support (Universal Gates)
        "hi": GenericLanguagePack("ENSURE HIGH RIGOR: Use formal, grammatically precise Hindi suitable for professional/medical contexts. Avoid colloquialisms."), 
        "ta": GenericLanguagePack("ENSURE HIGH RIGOR: Use formal, grammatically precise Tamil suitable for professional/medical contexts. Avoid colloquialisms."),
        "bn": GenericLanguagePack(), # Bengali
        "ko": GenericLanguagePack("ENSURE HIGH RIGOR: Use formal (Honorific/Polite) Korean suitable for professional/medical contexts."),
        "vi": GenericLanguagePack(), # Vietnamese
        "tr": GenericLanguagePack(), # Turkish
        "pl": GenericLanguagePack(), # Polish
        "nl": GenericLanguagePack(), # Dutch
        "th": GenericLanguagePack(), # Thai
        "id": GenericLanguagePack(), # Indonesian
        "el": GenericLanguagePack(), # Greek
    }
    
    @classmethod
    def get_pack(cls, lang_code: str) -> BaseLanguagePack:
        """
        Retrieves the appropriate LanguagePack using BCP 47 fallback logic.
        E.g. 'fr-CA' -> checks 'fr-ca' -> checks 'fr' -> returns GenericLanguagePack.
        """
        code = lang_code.lower()
        
        # 1. Exact Match
        if code in cls._packs:
            return cls._packs[code]
            
        # 2. Hierarchical Fallback (BCP 47)
        # Split by hyphen and try progressively shorter codes
        parts = code.split('-')
        while len(parts) > 1:
            parts.pop() # Remove last segment (e.g. 'CA' from 'fr-CA', or 'CN' from 'zh-Hans-CN')
            subcode = "-".join(parts)
            if subcode in cls._packs:
                return cls._packs[subcode]
                
        # 3. Default
        return GenericLanguagePack()
