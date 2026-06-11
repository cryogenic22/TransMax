"""
TMX-BB-SYNTH — the synthetic "Veridian Therapeutics" black book.

Two guarantees:
  1. The shipped dataset is well-formed (validates, expected coverage, forbidden
     terms present) — so the demo never claims coverage it lacks (A3).
  2. The loader seeds it tenant-scoped and is idempotent — re-running creates
     nothing new (A1/A4).
"""

import importlib.util
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location(
    "seed_synthetic_black_book", _SCRIPTS / "seed_synthetic_black_book.py"
)
assert _spec is not None and _spec.loader is not None
sbb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sbb)


def test_dataset_loads_and_validates():
    data = sbb.load_blackbook()
    assert data["org"]["org_slug"] == "veridian"
    assert len(data["glossaries"]) == 3


def test_dataset_covers_three_regulatory_pairs():
    data = sbb.load_blackbook()
    pairs = {(g["source_language"], g["target_language"]) for g in data["glossaries"]}
    assert pairs == {("en", "fr"), ("en", "de"), ("en", "es")}


def test_each_glossary_has_forbidden_terms():
    data = sbb.load_blackbook()
    for g in data["glossaries"]:
        forbidden = [t for t in g["terms"] if t["is_forbidden"]]
        assert len(forbidden) >= 4, (g["glossary_id"], len(forbidden))


def test_validate_rejects_duplicate_term_source():
    bad = {
        "org": {"org_slug": "x"},
        "glossaries": [
            {
                "glossary_id": "g",
                "version": "1",
                "source_language": "en",
                "target_language": "fr",
                "terms": [
                    {
                        "term_id": "a",
                        "source_text": "dup",
                        "target_text": "x",
                        "is_forbidden": False,
                    },
                    {
                        "term_id": "b",
                        "source_text": "dup",
                        "target_text": "y",
                        "is_forbidden": False,
                    },
                ],
            }
        ],
        "rules": [
            {
                "rule_id": "r",
                "source_pattern": "p",
                "target_correction": "c",
                "source_language": "en",
                "target_language": "fr",
            }
        ],
    }
    with pytest.raises(ValueError, match="duplicate source_text"):
        sbb.validate_blackbook(bad)


def test_seed_is_idempotent(fresh_engine_for_db):
    core_db = fresh_engine_for_db
    session = core_db.SessionLocal()
    try:
        data = sbb.load_blackbook()
        org_id = sbb.ensure_org(session, data["org"])

        first = sbb.seed_blackbook(session, org_id, data)
        assert first["glossaries"] == 3
        assert first["terms"] == sum(len(g["terms"]) for g in data["glossaries"])
        assert first["rules"] == len(data["rules"])

        # Second run must create nothing — idempotent.
        second = sbb.seed_blackbook(session, org_id, data)
        assert second == {"glossaries": 0, "terms": 0, "rules": 0}
    finally:
        session.close()


def test_seed_persists_forbidden_flag(fresh_engine_for_db):
    core_db = fresh_engine_for_db
    from app.core.tenant_context import org_context
    from app.models.models import GlossaryTerm

    session = core_db.SessionLocal()
    try:
        data = sbb.load_blackbook()
        org_id = sbb.ensure_org(session, data["org"])
        sbb.seed_blackbook(session, org_id, data)

        with org_context(org_id):
            forbidden_count = (
                session.query(GlossaryTerm)
                .filter(GlossaryTerm.is_forbidden.is_(True))
                .count()
            )
        assert forbidden_count >= 12  # >= 4 per glossary x 3
    finally:
        session.close()
