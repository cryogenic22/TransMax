"""Coverage / gross-omission detection (TMX-OMIT-1).

Pure logic for the completeness gate: did the target actually translate the
whole source, or did it silently drop sentences/paragraphs? The fine-grained
quality-gate checks (numbers/units/terms/symbols) only verify that *specific*
elements reappear; they stay silent when content with none of those — e.g. an
author list of names — is dropped. This module adds the missing check.

Char-ratio based (works across Latin/Arabic/CJK). Deliberately conservative:
the threshold sits below even the most compact legitimate language pair
(EN->ZH ~35-50% by char), so it fires on GROSS omission only — no false
positives on terse-but-complete translations (A3).
"""
from __future__ import annotations

# Below this fraction of source length, the target has almost certainly dropped
# content. EN->ZH (the most compact common pair) is ~0.35-0.5, so 0.20 is safe.
CRITICAL_RATIO = 0.20
# Segments shorter than this are too small to judge by ratio reliably.
MIN_SOURCE_CHARS = 40


def coverage_issue(source_text: str, target_text: str) -> str | None:
    """Return an omission message if the target grossly under-covers the source,
    else None. Untranslated/empty target and <20%-length target are flagged."""
    src = (source_text or "").strip()
    if len(src) < MIN_SOURCE_CHARS:
        return None

    tgt = (target_text or "").strip()
    if not tgt:
        return f"Untranslated: source has {len(src)} chars but the target is empty."

    src_chars = len(src.replace(" ", ""))
    tgt_chars = len(tgt.replace(" ", ""))
    if src_chars and (tgt_chars / src_chars) < CRITICAL_RATIO:
        ratio = tgt_chars / src_chars
        return (
            f"Critical omission: target is {ratio:.0%} of source length "
            f"({tgt_chars}/{src_chars} chars) — likely dropped content "
            f"(e.g. untranslated sentences). Verify completeness."
        )
    return None
