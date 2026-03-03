import re
from typing import List, Tuple, Dict, Optional

class PIIService:
    """
    Privacy Shield Service.
    Provides reversible PII masking to protect data sent to external LLMs.
    """
    
    # Default common patterns
    DEFAULT_PATTERNS = {
        "EMAIL": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "PHONE": r'\b(?:\+?1[-. ]?)?\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})\b',
        "SSN": r'\b\d{3}-\d{2}-\d{4}\b',
        "IPV4": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        "CREDIT_CARD": r'\b(?:\d{4}[-\s]?){3}\d{4}\b'
    }

    def __init__(self, patterns: Optional[Dict[str, str]] = None):
        """
        Initialize with optional custom patterns. 
        """
        self.patterns = self.DEFAULT_PATTERNS.copy()
        if patterns:
            self.patterns.update(patterns)

    def mask(self, text: str) -> Tuple[str, List[Dict[str, str]]]:
        """
        Reversibly masks PII in the text.
        Replaces entities with tokens like <EMAIL_1>, <PHONE_1>.
        
        Returns:
            Tuple(masked_text, redaction_map)
        """
        masked_text = text
        redaction_map = []
        
        # Counter for each type to ensure unique tokens e.g. <EMAIL_1>, <EMAIL_2>
        type_counters = {key: 1 for key in self.patterns}
        
        # We assume patterns are independent. 
        # For a robust implementation, we should handle overlapping matches (e.g. via interval tree)
        # But for this implementation, we process sequentially.
        
        for pii_type, pattern in self.patterns.items():
            matches = list(re.finditer(pattern, masked_text))
            # Process matches in reverse order to avoid index shifts affecting subsequent replacements
            # However, since we are replacing with Tokens that might contain similar chars/patterns,
            # we must be careful. 
            # Better approach: sequential replacement with unique tokens.
            # But re.sub is easier.
            
            # Since we need to track individual values for reversibility, re.sub with callback is best.
            
            def replace_callback(match):
                original_value = match.group(0)
                
                # Check if this is already a token (avoid double masking if patterns overlap?)
                # Unlikely with standard regexes, but good to note.
                
                token_id = type_counters[pii_type]
                token = f"<{pii_type}_{token_id}>"
                type_counters[pii_type] += 1
                
                redaction_map.append({
                    "token": token,
                    "original": original_value,
                    "type": pii_type
                })
                return token

            masked_text = re.sub(pattern, replace_callback, masked_text)
            
        return masked_text, redaction_map

    def unmask(self, masked_text: str, redaction_map: List[Dict[str, str]]) -> str:
        """
        Restores PII from the redaction map.
        Replace tokens <EMAIL_1> back to original values.
        """
        restored_text = masked_text
        
        # Sort map by token length or just iterate? 
        # Iterate clearly.
        for item in redaction_map:
            token = item['token']
            original = item['original']
            # Simple string replacement
            # We use replace() so if the LLM repeated the token, we restore all instances.
            restored_text = restored_text.replace(token, original)
            
        return restored_text

    def add_pattern(self, name: str, pattern: str):
        """Add a custom PII detection pattern."""
        self.patterns[name] = pattern

    def redact(self, text: str, mode: str = "mask") -> Tuple[str, List[Dict[str, str]]]:
        """
        Redact PII from text using <TYPE_REDACTED> tokens.
        mode='mask': replace with tokens, mode='remove': delete PII entirely.
        """
        redaction_map = []

        if mode == "remove":
            result = text
            for pii_type, pattern in self.patterns.items():
                matches = list(re.finditer(pattern, result))
                for match in reversed(matches):
                    redaction_map.append({
                        "token": "",
                        "original": match.group(0),
                        "type": pii_type
                    })
                    result = result[:match.start()] + result[match.end():]
            return result, redaction_map

        # Default mask mode
        masked_text = text
        for pii_type, pattern in self.patterns.items():
            def make_callback(pt):
                def replace_callback(match):
                    original_value = match.group(0)
                    token = f"<{pt}_REDACTED>"
                    redaction_map.append({
                        "token": token,
                        "original": original_value,
                        "type": pt
                    })
                    return token
                return replace_callback
            masked_text = re.sub(pattern, make_callback(pii_type), masked_text)
        return masked_text, redaction_map

# Singleton instance
default_pii_service = PIIService()
