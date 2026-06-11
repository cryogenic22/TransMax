"""
TMX-BB-FORBIDDEN — forbidden glossary terms are enforced end-to-end.

A GlossaryTerm flagged ``is_forbidden`` names a string that must NOT appear in
the translation (a deprecated regulatory phrasing such as the French
"effets secondaires"). This locks the two-hop path:

  GlossaryTerm.is_forbidden  ->  get_constraints()['forbidden_terms']
                             ->  QualityGateService critical/major defect

Pre-existing behavior (the wiring shipped with TMX-TERMLOCK-WB); this test
exists because that path had no regression guard and the constraint-builder
carried confused dead code that was cleaned up alongside it.
"""

from app.services.quality_gate import QualityGateService


def test_gate_fires_on_forbidden_term_in_target():
    qg = QualityGateService()
    defects = qg.check_segment(
        "Read the side effects section",
        "Lisez la rubrique effets secondaires",
        {"forbidden_terms": [{"term": "effets secondaires"}]},
        "fr",
    )
    assert any("Forbidden term" in d["message"] for d in defects), defects


def test_gate_silent_when_forbidden_term_absent():
    qg = QualityGateService()
    defects = qg.check_segment(
        "Read the side effects section",
        "Lisez la rubrique effets indésirables",
        {"forbidden_terms": [{"term": "effets secondaires"}]},
        "fr",
    )
    assert defects == []


def test_get_constraints_maps_is_forbidden_to_forbidden_terms():
    """Seed through DatabaseService's OWN session (it binds SessionLocal from
    app.models.database, not the test fixture's engine) under the seeded
    DEFAULT_ORG_ID, so the seed and get_constraints share one DB. Uses a unique
    glossary id so it is isolated from any other rows in the shared dev DB."""
    from app.core.tenant_context import org_context
    from app.models.database import DEFAULT_ORG_ID
    from app.models.models import Glossary, GlossaryTerm
    from app.services.db_service import DatabaseService

    svc = DatabaseService()
    gid = "g_fb_forbidden_test"
    session = svc.get_session()
    try:
        with org_context(DEFAULT_ORG_ID):
            if (
                session.query(Glossary).filter(Glossary.glossary_id == gid).first()
                is None
            ):
                session.add(
                    Glossary(
                        glossary_id=gid,
                        version="1.0.0",
                        organization_id=DEFAULT_ORG_ID,
                        is_active=True,
                    )
                )
                session.add(
                    GlossaryTerm(
                        organization_id=DEFAULT_ORG_ID,
                        glossary_id=gid,
                        glossary_version="1.0.0",
                        term_id="t1",
                        source_text="side effects",
                        target_text="effets secondaires",
                        is_forbidden=True,
                    )
                )
                session.add(
                    GlossaryTerm(
                        organization_id=DEFAULT_ORG_ID,
                        glossary_id=gid,
                        glossary_version="1.0.0",
                        term_id="t2",
                        source_text="adverse event",
                        target_text="événement indésirable",
                        is_forbidden=False,
                    )
                )
                session.commit()

            constraints = svc.get_constraints("en", "fr", glossary_id=gid)

        forbidden = [f["term"] for f in constraints["forbidden_terms"]]
        assert "effets secondaires" in forbidden
        # The non-forbidden term goes to the must-include glossary, not the blocklist.
        assert "effets secondaires" not in [
            g.get("target") for g in constraints["glossary"]
        ]
    finally:
        session.close()
