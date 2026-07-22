"""TMX-SEAM-CONTRACT — ADR-0009 clauses 3-5, v1 contract extension.

Schema-only: no route wiring is exercised here (see worksheet
`.context/loops/TMX-SEAM-CONTRACT.md` scope note). These tests pin the
shape reSCApe's generated client will bind against.
"""
from __future__ import annotations

import json

from app.schemas.api_v1 import (
    CONTRACT_VERSION,
    AuditBundleResponse,
    AuditRecordResponse,
    AuditRef,
    AuditVerificationResponse,
    ConstraintPack,
    JobCreateRequest,
    JobProfileRequest,
    JobResponse,
    JobResult,
    JobResultResponse,
    MqmSummary,
    OrgAuditVerificationResponse,
    ProvenanceRecord,
    SegmentResult,
    SourceReference,
    TermbaseRef,
    TranslationDisposition,
    ValidationSummary,
    tm_match_key,
)


def _base_profile() -> dict:
    return {"archetype": "INFORMATIONAL", "tier": "TIER_C", "modality": "NARRATIVE"}


def test_job_create_request_backwards_compatible_with_only_preexisting_fields() -> None:
    """AC-1: pre-existing callers (no source_ref, no constraints) still validate."""
    req = JobCreateRequest(
        source_language="en",
        target_language="fr",
        request_id="req-001",
        profile=JobProfileRequest(**_base_profile()),
        text_content="Take 10mg daily.",
    )
    assert req.source_ref is None
    assert req.constraints is None


def test_source_ref_and_constraints_round_trip_every_field() -> None:
    """AC-2: source_ref + constraints round-trip through model_validate/model_dump."""
    payload = {
        "source_language": "en",
        "target_language": "fr",
        "request_id": "req-002",
        "profile": _base_profile(),
        "text_content": "Take 10mg daily.",
        "source_ref": {
            "component_id": "comp-1",
            "component_version_id": "cv-7",
            "hash_canonical": "abc123",
            "doc_type": "SmPC",
            "market": "EU",
            "product_ref": "prod-9",
            "section_path": "4.2",
        },
        "constraints": {
            "termbase_refs": [{"termbase_id": "tb-1", "version": "3"}],
            "do_not_translate": ["Mounjaro", "5mg"],
        },
    }
    req = JobCreateRequest.model_validate(payload)
    assert req.source_ref is not None
    assert req.source_ref.component_id == "comp-1"
    assert req.source_ref.component_version_id == "cv-7"
    assert req.source_ref.hash_canonical == "abc123"
    assert req.source_ref.doc_type == "SmPC"
    assert req.source_ref.market == "EU"
    assert req.source_ref.product_ref == "prod-9"
    assert req.source_ref.section_path == "4.2"
    assert req.constraints is not None
    assert req.constraints.do_not_translate == ["Mounjaro", "5mg"]
    assert len(req.constraints.termbase_refs) == 1
    assert req.constraints.termbase_refs[0].termbase_id == "tb-1"
    assert req.constraints.termbase_refs[0].version == "3"

    dumped = req.model_dump()
    assert dumped["source_ref"]["hash_canonical"] == "abc123"
    assert dumped["constraints"]["do_not_translate"] == ["Mounjaro", "5mg"]


def _sample_mqm() -> MqmSummary:
    return MqmSummary(
        score=98.5,
        profile_id="smpc_pil",
        profile_version="1.0",
        critical_count=0,
        major_count=0,
        minor_count=1,
    )


def _sample_provenance() -> ProvenanceRecord:
    return ProvenanceRecord()


def _sample_audit_ref() -> AuditRef:
    return AuditRef()


def test_every_wired_response_model_carries_contract_version() -> None:
    """AC-3: every response model wired to a live route (per `response_model=` grep)
    plus the two new result-block models default contract_version to CONTRACT_VERSION.
    """
    assert CONTRACT_VERSION == "1.1.0"

    job_response = JobResponse(
        job_id="job-1", status="pending", created_at="2026-07-22T00:00:00Z"
    )
    assert job_response.contract_version == CONTRACT_VERSION

    job_result = JobResult(
        job_id="job-1",
        status="completed",
        original_filename="doc.txt",
        translated_text="Prenez 10mg par jour.",
        quality_summary=ValidationSummary(
            critical_count=0, major_count=0, minor_count=0, decision="PASS"
        ),
        audit_id="audit-1",
        completed_at="2026-07-22T00:00:00Z",
    )
    assert job_result.contract_version == CONTRACT_VERSION

    audit_bundle = AuditBundleResponse(
        audit_id="audit-1",
        job_id="job-1",
        final_decision="PASS",
        created_at="2026-07-22T00:00:00Z",
        chain_head_hash="deadbeef",
        is_tampered=False,
        entries=[],
    )
    assert audit_bundle.contract_version == CONTRACT_VERSION

    audit_record = AuditRecordResponse(
        audit_id="audit-1",
        job_id="job-1",
        final_decision="PASS",
        versions={},
        hash_signature="deadbeef",
        created_at="2026-07-22T00:00:00Z",
    )
    assert audit_record.contract_version == CONTRACT_VERSION

    audit_verification = AuditVerificationResponse(
        ok=True,
        status="OK",
        organization_id="org-1",
        job_id="job-1",
        event_count=1,
        ok_count=1,
        chain_head_hash="deadbeef",
        findings=[],
    )
    assert audit_verification.contract_version == CONTRACT_VERSION

    org_verification = OrgAuditVerificationResponse(
        organization_id="org-1", total_chains=1, ok_chains=1, all_ok=True, chains=[]
    )
    assert org_verification.contract_version == CONTRACT_VERSION

    segment_result = SegmentResult(
        segment_id="seg-1",
        disposition=TranslationDisposition.PASS,
        mqm=_sample_mqm(),
        provenance=_sample_provenance(),
        audit=_sample_audit_ref(),
    )
    assert segment_result.contract_version == CONTRACT_VERSION

    job_result_response = JobResultResponse(
        job_id="job-1",
        disposition=TranslationDisposition.PASS,
        segments=[segment_result],
        audit=_sample_audit_ref(),
    )
    assert job_result_response.contract_version == CONTRACT_VERSION


def test_tm_match_key_deterministic_and_bind_revalidates_on_termbase_change() -> None:
    """AC-4: same inputs -> same key; termbase_version_id change alone -> different key."""
    key_a = tm_match_key("hash-abc", "fr-FR", "tb-v1")
    key_b = tm_match_key("hash-abc", "fr-FR", "tb-v1")
    assert key_a == key_b

    key_c = tm_match_key("hash-abc", "fr-FR", "tb-v2")
    assert key_c != key_a


def test_translation_disposition_has_exactly_three_members() -> None:
    """AC-5: PASS / REVIEW_REQUIRED / BLOCKED, nothing else."""
    members = {member.value for member in TranslationDisposition}
    assert members == {"PASS", "REVIEW_REQUIRED", "BLOCKED"}


def test_export_contract_script_produces_valid_openapi_with_new_schema_names(tmp_path) -> None:
    """AC-6: `scripts/export_contract.py` produces valid JSON containing the
    new schema names, including the result-block models not wired to any
    live route this loop (see `_merge_unwired_contract_schemas`).
    """
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root / "scripts"))
    import export_contract

    output_path = tmp_path / "openapi.json"
    schema = export_contract.export_openapi(output_path)

    assert output_path.exists()
    with output_path.open(encoding="utf-8") as f:
        reloaded = json.load(f)
    assert reloaded == schema

    schemas = reloaded["components"]["schemas"]
    for name in (
        "SourceReference",
        "ConstraintPack",
        "TermbaseRef",
        "TranslationDisposition",
        "MqmSummary",
        "ProvenanceRecord",
        "AuditRef",
        "SegmentResult",
        "JobResultResponse",
    ):
        assert name in schemas, f"{name} missing from exported OpenAPI schema"
    assert reloaded["info"]["x-contract-version"] == CONTRACT_VERSION


def test_constraint_pack_and_source_reference_and_termbase_ref_all_optional_defaults() -> None:
    """Sanity: sub-models used by AC-2 have sane empty defaults (not tested by AC-1/AC-2 alone)."""
    ref = SourceReference()
    assert ref.component_id is None
    pack = ConstraintPack()
    assert pack.termbase_refs == []
    assert pack.do_not_translate == []
    tb = TermbaseRef(termbase_id="tb-1", version="1")
    assert tb.termbase_id == "tb-1"
