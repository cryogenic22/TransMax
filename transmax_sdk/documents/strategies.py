"""Segmentation strategies: sentence, paragraph, page."""

from __future__ import annotations

import re
from typing import List


class SentenceStrategy:
    """Splits text into sentences."""
    name = "sentence"

    # Sentence-ending pattern: period/question/exclamation followed by space or end
    PATTERN = re.compile(r'(?<=[.!?])\s+')

    def segment(self, text: str) -> List[str]:
        if not text.strip():
            return []
        segments = self.PATTERN.split(text.strip())
        return [s.strip() for s in segments if s.strip()]


class ParagraphStrategy:
    """Splits text into paragraphs (double newline separated)."""
    name = "paragraph"

    def segment(self, text: str) -> List[str]:
        if not text.strip():
            return []
        paragraphs = re.split(r'\n\s*\n', text.strip())
        return [p.strip() for p in paragraphs if p.strip()]


class PageStrategy:
    """Splits text into pages (form feed or page marker)."""
    name = "page"

    def segment(self, text: str) -> List[str]:
        if not text.strip():
            return []
        # Split on form feed or explicit page markers
        pages = re.split(r'\f|---PAGE BREAK---', text.strip())
        return [p.strip() for p in pages if p.strip()]
