"""TMX-SSOT-TIER — the funnel fix + tier→profile refinement + the one governance predicate.

The funnel tests use the fresh-DB fixture; the resolution + predicate tests are pure.
"""

import pytest

from app.core.metric_profiles.resolution import resolve_profile_id
from app.core.profile_enums import (
    ContentRiskTier,
    TranslationArchetype,
    is_tier_archetype_compatible,
)


def _make_org(core_db, slug):
    from app.models.database import Organization

    s = core_db.SessionLocal()
    org = Organization(name=slug, slug=slug, org_kind="customer")
    s.add(org)
    s.commit()
    oid = str(org.id)
    s.close()
    return oid


def _make_doc(core_db, org_id, meta, source_language="en"):
    from app.core.tenant_context import org_context
    from app.models.database import Document

    s = core_db.SessionLocal()
    with org_context(org_id):
        doc = Document(
            name="x.pdf",
            source_language=source_language,
            target_language="es",
            status="processing",
            organization_id=org_id,
            meta_json=meta,
        )
        s.add(doc)
        s.commit()
        did = doc.id
    s.close()
    return did


# ── Step 1: the funnel fix (reproduce-the-failure) ───────────────────────────
def test_get_document_metadata_returns_meta_json(fresh_engine_for_db, monkeypatch):
    core_db = fresh_engine_for_db
    monkeypatch.setattr(
        "app.services.db_service.SessionLocal", core_db.SessionLocal, raising=True
    )
    from app.core.tenant_context import org_context
    from app.services.db_service import get_db_service

    org = _make_org(core_db, "acme-ssot")
    doc = _make_doc(core_db, org, {"archetype": "OPERATIONAL", "tier": "TIER_A"})
    with org_context(org):
        # meta_json governance keys + the declared source_language column
        assert get_db_service().get_document_metadata(doc) == {
            "archetype": "OPERATIONAL",
            "tier": "TIER_A",
            "source_language": "en",
        }


def test_get_document_metadata_unknown_is_empty(fresh_engine_for_db, monkeypatch):
    core_db = fresh_engine_for_db
    monkeypatch.setattr(
        "app.services.db_service.SessionLocal", core_db.SessionLocal, raising=True
    )
    from app.core.tenant_context import org_context
    from app.services.db_service import get_db_service

    org = _make_org(core_db, "acme-ssot2")
    with org_context(org):
        assert get_db_service().get_document_metadata("nope") == {}


def test_get_document_metadata_surfaces_declared_source_language(
    fresh_engine_for_db, monkeypatch
):
    # The funnel resurrects the source-language node; surfacing the DECLARED
    # column keeps it deterministic: en stays 'en' (unchanged), de -> 'de'
    # (corrects the latent always-'en'), never fragile auto-detection.
    core_db = fresh_engine_for_db
    monkeypatch.setattr(
        "app.services.db_service.SessionLocal", core_db.SessionLocal, raising=True
    )
    from app.core.tenant_context import org_context
    from app.services.db_service import get_db_service

    org = _make_org(core_db, "acme-srclang")
    en_doc = _make_doc(
        core_db, org, {"archetype": "SAFETY_CRITICAL"}, source_language="en"
    )
    de_doc = _make_doc(
        core_db, org, {"archetype": "SAFETY_CRITICAL"}, source_language="de"
    )
    with org_context(org):
        assert get_db_service().get_document_metadata(en_doc)["source_language"] == "en"
        assert get_db_service().get_document_metadata(de_doc)["source_language"] == "de"


def test_funnel_now_selects_refined_profile(fresh_engine_for_db, monkeypatch):
    # Before the fix, get_document_metadata raised -> content_metadata {} ->
    # default smpc_pil. Now an OPERATIONAL+TIER_A doc resolves to the refined
    # strict profile through the real funnel (default OPERATIONAL would be 'pv').
    core_db = fresh_engine_for_db
    monkeypatch.setattr(
        "app.services.db_service.SessionLocal", core_db.SessionLocal, raising=True
    )
    from app.core.tenant_context import org_context
    from app.services.db_service import get_db_service

    org = _make_org(core_db, "acme-ssot3")
    doc = _make_doc(core_db, org, {"archetype": "OPERATIONAL", "tier": "TIER_A"})
    with org_context(org):
        meta = get_db_service().get_document_metadata(doc)
    content_metadata = {
        k: meta.get(k)
        for k in (
            "content_type",
            "doc_type",
            "document_type",
            "archetype",
            "tier",
            "metric_profile",
        )
        if meta.get(k) is not None
    }
    assert resolve_profile_id(content_metadata) == "smpc_pil"


# ── Step 2: tier refinement (default-preserving) ─────────────────────────────
def test_tier_a_refines_operational_to_strictest():
    assert (
        resolve_profile_id({"archetype": "OPERATIONAL", "tier": "TIER_A"}) == "smpc_pil"
    )


def test_tier_a_refines_analytical_to_strictest():
    assert (
        resolve_profile_id({"archetype": "ANALYTICAL", "tier": "TIER_A"}) == "smpc_pil"
    )


def test_tier_c_leaves_archetype_mapping_unchanged():
    assert resolve_profile_id({"archetype": "OPERATIONAL", "tier": "TIER_C"}) == "pv"


def test_tier_without_archetype_never_selects():
    # tier alone has no archetype to refine -> falls through to the default.
    assert resolve_profile_id({"tier": "TIER_A"}) == "smpc_pil"


def test_content_type_still_beats_archetype_tier():
    assert (
        resolve_profile_id(
            {"content_type": "icf", "archetype": "OPERATIONAL", "tier": "TIER_A"}
        )
        == "icf"
    )


def test_resolve_profile_id_handles_enum_members_not_just_strings():
    # str(ContentRiskTier.TIER_A) == 'ContentRiskTier.TIER_A' — a member must
    # resolve via .value, else it silently falls to the default profile.
    assert resolve_profile_id({"archetype": TranslationArchetype.OPERATIONAL}) == "pv"
    assert (
        resolve_profile_id({"archetype": TranslationArchetype.INFORMATIONAL}) == "promo"
    )
    assert (
        resolve_profile_id(
            {
                "archetype": TranslationArchetype.OPERATIONAL,
                "tier": ContentRiskTier.TIER_A,
            }
        )
        == "smpc_pil"
    )


# ── Step 3: unified governance predicate ─────────────────────────────────────
def test_predicate_blocks_informational_tier_a():
    assert (
        is_tier_archetype_compatible(
            TranslationArchetype.INFORMATIONAL, ContentRiskTier.TIER_A
        )
        is False
    )


def test_predicate_allows_other_combinations():
    assert (
        is_tier_archetype_compatible(
            TranslationArchetype.SAFETY_CRITICAL, ContentRiskTier.TIER_A
        )
        is True
    )
    assert (
        is_tier_archetype_compatible(
            TranslationArchetype.INFORMATIONAL, ContentRiskTier.TIER_C
        )
        is True
    )


def test_api_validator_still_raises_identical_message():
    from app.schemas.api_v1 import JobProfileRequest

    with pytest.raises(ValueError, match="Informational Archetype cannot be Tier A"):
        JobProfileRequest(
            archetype="INFORMATIONAL", tier="TIER_A", modality="NARRATIVE"
        )
