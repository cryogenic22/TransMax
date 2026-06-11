"""Back-translation semantic-drift scoring — extracted from quality_gate (TMX-3400-lite).

Source↔back-translation cosine similarity via OpenAI embeddings, scaled to a
0-100 score (100 = identical meaning). Returns ``None`` when the score cannot be
computed (no API key / embed failure) so callers can distinguish "no signal"
from a real low score (A3 — see TMX-DRIFT-SENTINEL).

Extracting this self-contained logic out of the 800-line ``quality_gate.py``
pays down part of the C-08 god-object debt and creates headroom for the gate to
grow (term-lock, etc.) without tripping the mega-file ceiling. ``QualityGateService``
keeps a thin delegating method so existing callers are unchanged.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def calculate_semantic_drift(source_text: str, back_translation: str) -> Optional[float]:
    """0-100 similarity (100=identical) or ``None`` if uncomputable (no key / embed fail)."""
    from langchain_openai import OpenAIEmbeddings
    from app.core.config import settings
    import numpy as np

    if not settings.openai_api_key:
        logger.warning("Semantic-drift unavailable: no OpenAI API key configured")
        return None

    try:
        embeddings_model = OpenAIEmbeddings(api_key=settings.openai_api_key)
        vecs = embeddings_model.embed_documents([source_text, back_translation])
        v1, v2 = np.array(vecs[0]), np.array(vecs[1])
        similarity = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        return float(max(0.0, min(100.0, similarity * 100)))
    except Exception as e:
        logger.warning(f"Semantic-drift calculation failed: {e}")
        return None
