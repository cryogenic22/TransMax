"""TMX-QRD-FR-HEADING — the FR SmPC profile must carry FRENCH QRD headings.

EMA_SMPC_FR_FR.mandatory_headings shipped with the English
"5. PHARMACOLOGICAL PROPERTIES" copy-pasted among five French headings.
Consumption path (quality_gate.py:check_mandatory_headers) is per-segment
membership: a segment that "looks like a numbered header" and is NOT in the
list fires STRUCTURE_ERROR. With English text in the FR list, an
UNTRANSLATED English section-5 heading in a French SmPC was silently
accepted (A3 vacuous green), and any future accent-aware header detection
would flag the CORRECT French heading as non-standard. These tests were red
before the registry fix and pin both directions, plus a repo-wide guard
against the copy-paste class.
"""

import re
from typing import Dict, List, Tuple

from app.core.defect_taxonomy import DefectCategory
from app.core.regulatory_profiles import REGULATORY_PROFILES
from app.services.quality_gate import QualityGateService

# Official QRD template, Annexe I — Résumé des Caractéristiques du Produit
# (top-level sections at the granularity this registry uses for EN siblings).
OFFICIAL_FR_SMPC_HEADINGS = [
    "1. DÉNOMINATION DU MÉDICAMENT",
    "2. COMPOSITION QUALITATIVE ET QUANTITATIVE",
    "3. FORME PHARMACEUTIQUE",
    "4. DONNÉES CLINIQUES",
    "5. PROPRIÉTÉS PHARMACOLOGIQUES",
    "6. DONNÉES PHARMACEUTIQUES",
]


def test_french_smpc_with_all_official_headings_passes_mandatory_check() -> None:
    """AC-1 + AC-2: a correct French SmPC passes the mandatory-heading check.

    "Passes the check" requires BOTH: (a) every official French heading is a
    member of the profile's mandatory list — a heading the registry does not
    list can never satisfy the mandatory-heading contract (today headings with
    accents are skipped only by accident of the checker's ASCII-only header
    regex, a separate latent bug); and (b) no official heading produces a
    STRUCTURE_ERROR through the real checker. (a) was red pre-fix: the list
    demanded English text for section 5.
    """
    profile = REGULATORY_PROFILES["EMA_SMPC_FR_FR"]
    assert profile["mandatory_headings"] == OFFICIAL_FR_SMPC_HEADINGS

    gate = QualityGateService()
    for heading in OFFICIAL_FR_SMPC_HEADINGS:
        defects = gate.check_mandatory_headers(heading, "EMA_SMPC_FR_FR")
        structure_errors = [
            d for d in defects if d.category is DefectCategory.STRUCTURE_ERROR
        ]
        assert not structure_errors, (
            f"Correct French heading flagged as non-standard: {heading!r} "
            f"-> {[d.message for d in structure_errors]}"
        )


def test_untranslated_english_heading_fires_in_french_profile() -> None:
    """AC-3: English section-5 heading under the FR profile must FIRE.

    Red pre-fix: "5. PHARMACOLOGICAL PROPERTIES" was IN the FR mandatory
    list, so the gate silently accepted an untranslated heading in a French
    SmPC — an unearned green on the regulated path (A3).
    """
    gate = QualityGateService()
    defects = gate.check_mandatory_headers(
        "5. PHARMACOLOGICAL PROPERTIES", "EMA_SMPC_FR_FR"
    )
    assert any(d.category is DefectCategory.STRUCTURE_ERROR for d in defects), (
        "Untranslated English heading was silently accepted by the "
        "EMA_SMPC_FR_FR mandatory-heading check"
    )


# Guard across the whole registry: obviously-English marker words must not
# appear in any non-English-locale profile's mandatory headings. Word-boundary
# match so cognates in other languages (e.g. Dutch KLINISCHE, French
# PHARMACEUTIQUE) can never false-positive the guard.
_ENGLISH_MARKERS = re.compile(r"\b(PROPERTIES|CLINICAL|PHARMACEUTICAL|PARTICULARS)\b")

# Documented allowlist for legitimate collisions: (profile_id, heading) -> why.
# Currently empty — no non-EN authority uses these exact English tokens.
_ALLOWED_COLLISIONS: Dict[Tuple[str, str], str] = {}


def test_no_english_marker_words_in_non_english_profile_headings() -> None:
    """AC-4: repo-wide guard against the EN->XX copy-paste class."""
    offenders: List[Tuple[str, str]] = []
    for pid, profile in REGULATORY_PROFILES.items():
        if profile["locale"].startswith("en"):
            continue
        for heading in profile["mandatory_headings"]:
            if not _ENGLISH_MARKERS.search(heading):
                continue
            if (pid, heading) in _ALLOWED_COLLISIONS:
                continue
            offenders.append((pid, heading))
    assert not offenders, (
        f"English marker words in non-EN profile mandatory headings "
        f"(copy-paste from an EN profile?): {offenders}"
    )
