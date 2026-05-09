"""
Frequency-pattern data for QualityGateService.check_frequency.

Extracted from `quality_gate.py` in TMX-3411 to keep that file under the
800-line ratchet threshold and to separate language-specific data from
gate logic. Adding patterns for a new language only touches this module.

Patterns are stored unaccented and NFC-recomposed; callers fold input
text the same way before lookup. See `_fold_for_lookup()`.
"""
from __future__ import annotations

import unicodedata


# Pharma frequency abbreviations -> canonical frequency per day.
FREQ_MAP: dict[str, float] = {
    "qd": 1.0, "once daily": 1.0, "once a day": 1.0,
    "bid": 2.0, "twice daily": 2.0, "twice a day": 2.0,
    "tid": 3.0, "three times daily": 3.0, "three times a day": 3.0,
    "qid": 4.0, "four times daily": 4.0, "four times a day": 4.0,
    "qhs": 1.0,  # at bedtime
}


# Multilingual frequency patterns. Each block adds one language's canonical
# 1×/d through 4×/d phrasings. Patterns stored unaccented (NFKD-folded) so
# the lookup folds input the same way and matches without doubling entries.
# History:
#   - EN/FR landed pre-Sprint 1 with the original gate.
#   - Spanish added in TMX-3409 (eval `good_001`).
#   - DE/IT/PT/KO/ZH/JA/AR added in TMX-3411 (cross-language sweep).
FREQ_PATTERNS: dict[str, float] = {
    # English
    "once daily": 1.0,
    "twice daily": 2.0,
    "three times daily": 3.0,
    "four times daily": 4.0,
    # French
    "une fois par jour": 1.0,
    "deux fois par jour": 2.0,
    "trois fois par jour": 3.0,
    "quatre fois par jour": 4.0,
    # Spanish (TMX-3409)
    "una vez al dia": 1.0,
    "dos veces al dia": 2.0,
    "tres veces al dia": 3.0,
    "cuatro veces al dia": 4.0,
    # German (TMX-3411) — "täglich" NFKD-folds to "taglich"
    "einmal taglich": 1.0,
    "zweimal taglich": 2.0,
    "dreimal taglich": 3.0,
    "viermal taglich": 4.0,
    # Italian (TMX-3411)
    "una volta al giorno": 1.0,
    "due volte al giorno": 2.0,
    "tre volte al giorno": 3.0,
    "quattro volte al giorno": 4.0,
    # Portuguese (TMX-3411) — "três" folds to "tres"; covers pt-BR + pt-PT
    "uma vez ao dia": 1.0,
    "uma vez por dia": 1.0,
    "duas vezes ao dia": 2.0,
    "duas vezes por dia": 2.0,
    "tres vezes ao dia": 3.0,
    "tres vezes por dia": 3.0,
    "quatro vezes ao dia": 4.0,
    "quatro vezes por dia": 4.0,
    # Korean (TMX-3411) — numeric and native ordinal forms
    "1일 1회": 1.0,
    "하루 한 번": 1.0,
    "1일 2회": 2.0,
    "하루 두 번": 2.0,
    "1일 3회": 3.0,
    "하루 세 번": 3.0,
    "1일 4회": 4.0,
    "하루 네 번": 4.0,
    # Chinese (TMX-3411) — Simplified + Traditional canonical phrasings
    "每日一次": 1.0,
    "一天一次": 1.0,
    "每日两次": 2.0,
    "每日二次": 2.0,
    "一天两次": 2.0,
    "每日三次": 3.0,
    "一天三次": 3.0,
    "每日四次": 4.0,
    # Japanese (TMX-3411) — half-width and full-width digits, kanji ordinals
    "1日1回": 1.0,
    "一日一回": 1.0,
    "1日2回": 2.0,
    "一日二回": 2.0,
    "1日3回": 3.0,
    "一日三回": 3.0,
    "1日4回": 4.0,
    "一日四回": 4.0,
    # Arabic (TMX-3411) — patterns post-NFKD-fold (alef+hamza decomposes)
    "مرة في اليوم": 1.0,
    "مرة يوميا": 1.0,
    "مرتين في اليوم": 2.0,
    "مرتين يوميا": 2.0,
    "ثلاث مرات في اليوم": 3.0,
    "اربع مرات في اليوم": 4.0,
}


def fold_for_lookup(s: str) -> str:
    """
    Normalise text for FREQ_PATTERNS lookup.

    Steps:
      1. NFKD decompose ("día" -> "di" + acute, "täglich" -> "taglich" + diaeresis)
      2. Strip combining marks (Latin diacritics removed; Korean Jamo kept)
      3. NFC recompose (Korean Jamo precomposes back to syllable blocks so
         precomposed patterns in FREQ_PATTERNS match)

    Without the trailing NFC, Korean Hangul stays Jamo-decomposed and never
    matches precomposed patterns — see TMX-3411.
    """
    decomposed = unicodedata.normalize("NFKD", s)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", stripped)
