"""TMX-OMIT-1 — coverage/omission gate.

Reproduces the failure: a long source whose target dropped ~90% of the content
(an author list) was reported OK. The coverage gate must flag it CRITICAL, and
the fine-grained gates' silence is replaced by an explicit completeness check —
without false-positiving on legitimately-compact languages.
"""
from __future__ import annotations

from app.core.defect_taxonomy import DefectCategory, DefectSeverity, is_critical
from app.services.quality_gate import QualityGateService

QG = QualityGateService()

# A realistic long source (funding + title + author byline, like NEJM seg #25).
LONG_SOURCE = (
    "(Funded by BioNTech and Pfizer; ClinicalTrials.gov number, NCT04368728.) "
    "abstract Safety and Efficacy of the BNT162b2 mRNA Covid-19 Vaccine "
    "Fernando P. Polack, M.D., Stephen J. Thomas, M.D., Nicholas Kitchin, M.D., "
    "Judith Absalon, M.D., Alejandra Gurtman, M.D., Stephen Lockhart, D.M., "
    "John L. Perez, M.D., Gonzalo Perez Marc, M.D., Edson D. Moreira, M.D., "
    "Cristiano Zerbini, M.D., Ruth Bailey, B.Sc., Kena A. Swanson, Ph.D., "
    "Satrajit Roychoudhury, Ph.D., Kenneth Koury, Ph.D., Ping Li, Ph.D., "
    "Warren V. Kalina, Ph.D., David Cooper, Ph.D., Robert W. Frenck, Jr., M.D., "
    "Laura L. Hammitt, M.D., Ozlem Tureci, M.D., Haylene Nell, M.D., "
    "Axel Schaefer, M.D., Serhat Unal, M.D., Dina B. Tresnan, D.V.M., Ph.D., "
    "Susan Mather, M.D., Philip R. Dormitzer, M.D., Ph.D., Ugur Sahin, M.D., "
    "Kathrin U. Jansen, Ph.D., and William C. Gruber, M.D., for the C4591001 "
    "Clinical Trial Group. The New England Journal of Medicine is produced by "
    "NEJM Group, a division of the Massachusetts Medical Society."
)
# Target that dropped the whole author list + closing sentence (~10% of source).
DROPPED_TARGET = (
    "(بتمويل من BioNTech و Pfizer؛ رقم ClinicalTrials.gov، NCT04368728.) "
    "ملخص سلامة وفعالية لقاح BNT162b2 mRNA لكوفيد-19."
)


def _coverage_defects(violations):
    return [v for v in violations if v["category"] == DefectCategory.OMISSION.value]


def test_gross_omission_is_flagged_critical():
    """The exact author-list-drop case: flagged as CRITICAL OMISSION (not OK)."""
    violations = QG.check_segment(LONG_SOURCE, DROPPED_TARGET, {}, "ar")
    omissions = _coverage_defects(violations)
    assert len(omissions) >= 1, "gross omission must be flagged"
    assert omissions[0]["severity"] == DefectSeverity.CRITICAL.value
    assert is_critical(omissions[0]["severity"])


def test_empty_target_flagged_untranslated():
    violations = QG.check_segment(LONG_SOURCE, "", {}, "ar")
    omissions = _coverage_defects(violations)
    assert any("Untranslated" in o["message"] for o in omissions)
    assert omissions[0]["severity"] == DefectSeverity.CRITICAL.value


def test_complete_translation_not_flagged():
    """A full-length translation produces no omission flag."""
    src = "Safe and effective vaccines are urgently needed to control the pandemic."
    tgt = "Se necesitan urgentemente vacunas seguras y eficaces para controlar la pandemia."
    omissions = _coverage_defects(QG.check_segment(src, tgt, {}, "es"))
    assert omissions == []


def test_compact_language_not_false_flagged():
    """A legitimately-compact target (≈35-50% chars, e.g. EN→ZH) is NOT flagged
    — the 20% threshold sits below any real translation."""
    src = "Safety and Efficacy of the BNT162b2 mRNA Covid-19 Vaccine in adults"
    tgt = "BNT162b2 mRNA 新冠疫苗在成人中的安全性和有效性研究结果"  # ~40% of source chars
    omissions = _coverage_defects(QG.check_segment(src, tgt, {}, "zh"))
    assert omissions == [], f"false positive on compact language: {omissions}"


def test_short_segment_skipped():
    """Short segments (ratio noisy) aren't coverage-checked."""
    omissions = _coverage_defects(QG.check_segment("Take 5 mg.", "5 mg.", {}, "de"))
    assert omissions == []
