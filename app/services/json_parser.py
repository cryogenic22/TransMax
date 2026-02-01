import json
import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class RobustParser:
    """
    Utility to extract valid JSON from LLM responses 
    that might contain markdown, trailing text, or slight malformations.
    """
    
    @staticmethod
    def parse(content: str) -> Dict[str, Any]:
        """
        Attempts to parse JSON from a string string.
        Raises ValueError if unrecoverable.
        """
        if not content:
             raise ValueError("Empty content")
             
        # 1. Try direct parse
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.debug(f"Direct JSON parse failed: {e}")
            
        # 2. Strip Markdown Code Blocks
        # Matches ```json ... ``` or just ``` ... ```
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if match:
            clean_content = match.group(1).strip()
            try:
                return json.loads(clean_content)
            except json.JSONDecodeError as e:
                 # If block content is bad, fall through to regex search
                 logger.debug(f"Markdown block parse failed: {e}")

        # 3. Regex Search for first JSON object
        # Finds the first { ... } pair. 
        # Naive: assuming non-nested or basic structure. 
        # Better: Search from first '{' to last '}'
        start = content.find('{')
        end = content.rfind('}')
        
        if start != -1 and end != -1 and end > start:
            possible_json = content[start : end + 1]
            try:
                return json.loads(possible_json)
            except json.JSONDecodeError as e:
                logger.debug(f"Regex extraction parse failed: {e}")
                
        # 4. Failed all heuristics
        raise ValueError(f"Could not extract JSON from content: {content[:100]}...")
