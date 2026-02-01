
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class Violation(Dict[str, Any]):
    """Type alias for a violation dictionary."""
    pass

class BaseLanguagePack(ABC):
    """
    Abstract base class for Language Drivers.
    Each language pack implements specific validation logic for its script/locale.
    """
    
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
