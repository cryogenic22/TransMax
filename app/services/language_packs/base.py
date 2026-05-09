
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class Violation(Dict[str, Any]):
    """Type alias for a violation dictionary."""
    pass

class BaseLanguagePack(ABC):
    """
    Abstract base class for Language Drivers.
    Each language pack implements specific validation logic for its script/locale.
    """

    def _find_missing_numbers(
        self,
        source_text: str,
        target_text: str,
        *,
        accept_decimal_swap: bool = False,
        digit_translate: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        # Critical safety: substring `in` is unsafe (e.g. '10' is contained in
        # '100', silently passing 10 mg -> 100 mg dose tampering). Use a
        # digit-only boundary instead of `\b` — `\b` fails when digits sit
        # next to CJK ideographs (`用500毫`) or to letters (`10mg`) because
        # both sides are `\w` in Python 3 Unicode regex. See TMX-3408 /
        # TMX-3410 / TMX-3410-fix.
        nums = re.findall(r'\d+(?:[.,]\d+)?', source_text)
        missing: List[str] = []
        for num in nums:
            forms = {num}
            if accept_decimal_swap:
                if '.' in num:
                    forms.add(num.replace('.', ','))
                if ',' in num:
                    forms.add(num.replace(',', '.'))
            if digit_translate:
                trans_table = str.maketrans(digit_translate)
                forms.add(num.translate(trans_table))
            found = any(
                re.search(rf'(?<!\d){re.escape(form)}(?!\d)', target_text)
                for form in forms
            )
            if not found:
                missing.append(num)
        return missing
    
    @property
    @abstractmethod
    def code(self) -> str:
        """ISO language code (e.g., 'ar', 'ja')."""
        pass

    @property
    @abstractmethod
    def script_direction(self) -> str:
        """'ltr' or 'rtl'."""
        pass

    def check_negation(self, source_text: str, target_text: str) -> List[Dict[str, Any]]:
        """
        Check if negation logic is preserved.
        """
        return []

    def check_numbers(self, source_text: str, target_text: str) -> List[Dict[str, Any]]:
        """
        Check if numbers are preserved, respecting digit policies.
        """
        return []

    def check_punctuation(self, target_text: str) -> List[Dict[str, Any]]:
        """
        Check for script-specific punctuation requirements.
        """
        return []
        
    def check_variants(self, target_text: str) -> List[Dict[str, Any]]:
        """
        Check for mandatory or restricted variants.
        """
        return []

    def check_placeholders(self, source_text: str, target_text: str) -> List[Dict[str, Any]]:
        """
        Check if placeholders ({{var}}, [1]) are preserved exactly.
        TMX-034: Critical safety gate.
        """
        return []

    def extract_frequency(self, text: str) -> List[Dict[str, Any]]:
        """
        Extracts dosing frequency info.
        Returns list of {"count": float, "interval": str (day/week), "raw": str}
        TMX-031: Critical Safety.
        """
        return []
        
    @property
    def prompt_instruction(self) -> str:
        """
        Specific instructions to inject into the LLM system prompt for this language.
        Used for enforcing register, script variants, or specific rigor.
        """
        return ""
