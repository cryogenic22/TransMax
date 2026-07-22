import hashlib
import json
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.core.profile_enums import (
    ContentRiskTier,
    OutputModality,
    TranslationArchetype,
    is_tier_archetype_compatible,
)

# TMX-SEAM-CONTRACT / ADR-0009 clause 3: the join key a stored result is traced
# back to. Bump whenever a response shape changes; existing routes stay on the
# same version until their shape actually changes (backwards-compatible
# additions don't require a bump per CROSS-REPO-PROTOCOL Rule 3, but this loop
# starts the seam contract at 1.1.0 per the ticket).
CONTRACT_VERSION = "1.1.0"


class SourceReference(BaseModel):
    """ADR-0009 clause 3 — reSCApe component identity a translation job was run
    against. All fields optional: TransMax accepts jobs with no reSCApe origin
    (e.g. ad-hoc translation) as well as seam-originated ones (A5: these IDs
    are carried through verbatim, never re-derived from position or content).
    """
    component_id: Optional[str] = None
    component_version_id: Optional[str] = None
    hash_canonical: Optional[str] = None
    doc_type: Optional[str] = None
    market: Optional[str] = None
    product_ref: Optional[str] = None
    section_path: Optional[str] = None


class TermbaseRef(BaseModel):
    """One versioned termbase reference inside a `ConstraintPack`."""
    termbase_id: str
    version: str


class ConstraintPack(BaseModel):
    """ADR-0009 clause 3 — constraints a translation job must honour.

    `termbase_refs` carries the versioned termbase(s) to apply; the version is
    part of `tm_match_key` below so a terminology change invalidates any TM
    match automatically (ADR-0009 clause 4 bind-revalidation).
    """
    termbase_refs: List[TermbaseRef] = Field(default_factory=list)
    do_not_translate: List[str] = Field(default_factory=list)


class JobProfileRequest(BaseModel):
    """
    TMX-GOV-03: Governance Profile.
    Defines the rigor level for the translation job.
    """
    archetype: TranslationArchetype = Field(..., description="Governance Archetype")
    tier: ContentRiskTier = Field(..., description="Risk Tier (A=Highest, C=Lowest)")
    modality: OutputModality = Field(..., description="Target format/modality")
    # TMX-QRD-WIRE: optional regulatory profile id (e.g. "EMA_SMPC_EN_GB").
    # Backwards-compatible (defaults None). When set + enable_qrd_checks is on,
    # the gate enforces that authority's date-format + mandatory-header rules.
    regulatory_profile: Optional[str] = Field(
        None, description="Optional regulatory profile id enabling QRD checks (e.g. EMA_SMPC_EN_GB)"
    )
    
    @field_validator('tier')
    @classmethod
    def validate_tier_archetype_compatibility(cls, v, info):
        """
        Enforce Governance Invariants at the Edge (TMX-SSOT-TIER: one predicate).
        Example: INFORMATIONAL cannot be TIER_A.
        """
        if 'archetype' in info.data and not is_tier_archetype_compatible(info.data['archetype'], v):
            raise ValueError("Informational Archetype cannot be Tier A (Critical).")
        return v

class JobCreateRequest(BaseModel):
    """
    TMX-010: Job Creation Schema.
    """
    source_language: str = Field(..., min_length=2, max_length=5, json_schema_extra={"example": "en"})
    target_language: str = Field(..., min_length=2, max_length=5, json_schema_extra={"example": "ja"})
    
    request_id: str = Field(..., description="Idempotency Key")
    
    # Nested strict profile
    profile: JobProfileRequest
    
    # Metadata
    domain: str = Field("pharma", description="Industry domain")
    
    # Content
    text_content: Optional[str] = None
    document_name: Optional[str] = "untitled.txt"
    
    # Async Callback. TMX-WEBHOOK-FIRE: dispatched on terminal job status by
    # app/services/webhook_dispatch.py — no longer accepted-and-ignored (A3).
    webhook_url: Optional[HttpUrl] = None

    # TMX-SEAM-CONTRACT / ADR-0009 clause 3: reSCApe origin + constraints.
    # Both optional and default-None — pre-existing callers (no seam origin)
    # are unaffected. NOT wired into the live translation path this loop
    # (schema + helper + export only; see worksheet scope note).
    source_ref: Optional[SourceReference] = None
    constraints: Optional[ConstraintPack] = None

    @field_validator('webhook_url')
    @classmethod
    def validate_webhook_target(cls, v: Optional[HttpUrl]) -> Optional[HttpUrl]:
        """TMX-WEBHOOK-FIRE SSRF guard.

        Reject private/loopback/link-local webhook targets with a 422 unless
        `Settings.webhook_allow_private_targets` (default False) is set —
        otherwise a tenant could aim the platform's egress at internal
        infrastructure (169.254.169.254 metadata, localhost admin ports, …).
        Imports are lazy to keep the schema layer import-light; the host
        predicate lives in the dispatch service so schema and dispatcher can
        never drift (single source of truth).
        """
        if v is None:
            return v
        from app.core.config import settings
        from app.services.webhook_dispatch import is_private_webhook_host

        if settings.webhook_allow_private_targets:
            return v
        if is_private_webhook_host(v.host or ""):
            raise ValueError(
                "webhook_url must not target a private, loopback, or "
                "link-local host; webhook delivery to internal networks is "
                "disabled (WEBHOOK_ALLOW_PRIVATE_TARGETS is for trusted "
                "dev/test environments only)."
            )
        return v

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "source_language": "en",
            "target_language": "fr",
            "request_id": "req-001",
            "profile": {
                "archetype": "SAFETY_CRITICAL",
                "tier": "TIER_A",
                "modality": "NARRATIVE"
            },
            "text_content": "Take 10mg daily.",
            "domain": "pharma"
        }
    })

class Alert(BaseModel):
    severity: str
    message: str

class ValidationSummary(BaseModel):
    critical_count: int
    major_count: int
    minor_count: int
    decision: str
    semantic_drift: Optional[int] = None


# ---------------------------------------------------------------------------
# TMX-SEAM-CONTRACT / ADR-0009 clause 3 — shared result-block component
# models. Moved above `JobResult` (TMX-SEAM-WIRE) so `JobResult` can carry
# them as optional fields without a forward reference. `SegmentResult` /
# `JobResultResponse` (further below) still compose these; nothing about
# their shape changes.
# ---------------------------------------------------------------------------

class TranslationDisposition(str, Enum):
    """ADR-0009 clause 3 — the gate verdict a segment or job carries."""
    PASS = "PASS"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


class MqmSummary(BaseModel):
    """The MQM 2.0 score and the exact profile version that produced it (A6/A8:
    reproducibility — a regulator must be able to trace a score to a pinned
    profile version, never an unversioned "current" profile).
    """
    score: float
    profile_id: str
    profile_version: str
    critical_count: int
    major_count: int
    minor_count: int


class ProvenanceRecord(BaseModel):
    """A6 qualified-supplier telemetry for the LLM call (or TM match) that
    produced a segment. All fields optional: a value is only ever populated
    from the artefact that produced it (prompt hash, chain entry, match
    type) — never defaulted or a fallback survivor (A3/ADR-0009 clause 5).
    """
    model: Optional[str] = None
    model_version: Optional[str] = None
    prompt_version: Optional[str] = None
    prompt_content_hash: Optional[str] = None
    match_type: Optional[str] = None
    language_tier: Optional[str] = None


class AuditRef(BaseModel):
    """A1/C-8: every result carries a pointer into the tamper-evident chain
    and a URL that independently re-verifies it — never just a claim.
    """
    chain_head_hash: Optional[str] = None
    verify_url: Optional[str] = None


class JobResponse(BaseModel):
    """
    TMX-010: Job Status Response.
    """
    job_id: str
    status: str
    confidence_score: Optional[float] = None
    score_breakdown: Optional[Dict[str, float]] = None
    created_at: datetime
    estimated_completion: Optional[datetime] = None
    # TMX-SEAM-CONTRACT: join key — see CONTRACT_VERSION docstring above.
    contract_version: str = CONTRACT_VERSION

class JobResult(BaseModel):
    """
    TMX-010: Final Result Payload.
    """
    job_id: str
    status: str
    original_filename: Optional[str]

    translated_text: Optional[str]
    quality_summary: ValidationSummary
    audit_id: Optional[str]

    completed_at: datetime
    contract_version: str = CONTRACT_VERSION

    # TMX-SEAM-WIRE / ADR-0009 clause 3: the result block, wired to the live
    # verdict + provenance + audit pointer honestly (A3). All four fields are
    # optional and additive — pre-existing callers reading only the fields
    # above are unaffected (AC-4).
    #
    # `disposition` is derived from the REAL persisted `QualityScorecard.status`
    # (the legacy count-based `evaluate_verdict` verdict) — never re-derived
    # from `doc.status` (workflow state, a different concept).
    disposition: Optional[TranslationDisposition] = None
    # `provenance` fields are populated ONLY from the job's real
    # CONFIG_SNAPSHOT_CAPTURED v2 audit event (the same payload
    # `_config_snapshot.build_config_snapshot` produced at job start) plus the
    # segments' real `translation_source`. Any field with no artefact to back
    # it (e.g. `model_version`, `language_tier` — no such artefact exists in
    # this codebase yet) stays None.
    provenance: Optional[ProvenanceRecord] = None
    # `audit` is populated ONLY from the job's real v2 audit chain
    # (`AuditEventV2`); None if the job has no v2 chain — never a placeholder.
    audit: Optional[AuditRef] = None
    # `mqm` MUST stay None: the MQM engine is shadow-only (TMX-MQM-5 series)
    # and has no consumer on the live verdict — `disposition` above still
    # comes from the legacy scorer. Synthesizing an MqmSummary here from the
    # legacy scorer would be the exact unearned-claim defect this program
    # keeps fixing (A3). This becomes real at the TMX-MQM-5b cutover, when
    # the MQM verdict actually becomes the live one.
    mqm: Optional[MqmSummary] = None

class AuditLogEntryResponse(BaseModel):
    sequence_index: int
    event_type: str
    timestamp: datetime
    entry_hash: str
    payload_summary: Optional[Dict[str, Any]]

class AuditBundleResponse(BaseModel):
    """
    TMX-020: Regulatory Audit Bundle Export.
    """
    audit_id: str
    job_id: str
    final_decision: str
    created_at: datetime
    
    chain_head_hash: str
    is_tampered: bool

    entries: List[AuditLogEntryResponse]
    contract_version: str = CONTRACT_VERSION

class AuditRecordResponse(BaseModel):
    """
    TMX-020: Detailed Audit Record View.
    """
    audit_id: str
    job_id: Optional[str]
    final_decision: Optional[str]
    versions: Dict[str, Optional[str]]
    hash_signature: Optional[str]
    full_payload: Optional[Dict[str, Any]] = None
    created_at: datetime
    contract_version: str = CONTRACT_VERSION


class VerifyFinding(BaseModel):
    """
    TMX-3105: One defect surfaced by the v2 audit verifier.

    Mirrors `app.services.audit_verifier_v2.EventReport`. Wire format is
    stable: the regulator-facing reviewer reads `finding` as the
    machine-stable classifier string and `detail` as human prose.
    """
    event_id: str
    sequence_index: int
    finding: str = Field(
        ...,
        description=(
            "One of: ok, tampered_payload, tampered_event_hash, "
            "broken_chain, sequence_gap, sequence_duplicate, "
            "invalid_hash_length, genesis_violation."
        ),
    )
    detail: Optional[str] = None


class AuditVerificationResponse(BaseModel):
    """
    TMX-3105: Independent verification result for a v2 audit chain.

    `ok` is true iff the verifier found zero defects across the chain.
    A3-loud: a tampered chain returns `ok=False` with populated
    `findings`, NEVER an empty findings list with `ok=True`.

    TMX-3105a: `status` is a single machine-stable headline the reviewer UI
    renders as a badge without parsing the findings array; `chain_head_hash`
    is the hex `event_hash` of the latest event, the value a regulator
    anchors against the daily Merkle root / external timestamp.
    """
    ok: bool = Field(..., description="True iff zero defects detected.")
    status: str = Field(
        ...,
        description=(
            "Headline verdict: OK (clean) | TAMPERED (hash/payload/chain "
            "defect) | SEQUENCE_GAP (missing or duplicate sequence) | EMPTY "
            "(no events). Derived from findings; `ok == (status == 'OK')`."
        ),
    )
    organization_id: str
    job_id: str
    event_count: int
    ok_count: int
    chain_head_hash: Optional[str] = Field(
        None,
        description="Hex event_hash of the highest-sequence event; null for an empty chain.",
    )
    findings: List[VerifyFinding] = Field(default_factory=list)
    contract_version: str = CONTRACT_VERSION


class OrgChainSummary(BaseModel):
    """TMX-VERIFY-ORG: one job's verdict in an org-wide verification sweep."""
    job_id: str
    ok: bool
    status: str = Field(..., description="OK | TAMPERED | SEQUENCE_GAP | EMPTY")
    event_count: int
    ok_count: int


class OrgAuditVerificationResponse(BaseModel):
    """
    TMX-VERIFY-ORG: independent verification of EVERY v2 chain owned by the
    current tenant, in one regulator-facing call.

    `all_ok` is the single gate a compliance dashboard reads: true iff every
    chain verified clean. A3-loud: any tampered/gapped chain flips `all_ok`
    to false and is itemised in `chains`.
    """
    organization_id: str
    total_chains: int
    ok_chains: int
    all_ok: bool
    chains: List[OrgChainSummary] = Field(default_factory=list)
    contract_version: str = CONTRACT_VERSION


# ---------------------------------------------------------------------------
# TMX-SEAM-CONTRACT / ADR-0009 clause 3 — the result block.
#
# `TranslationDisposition` / `MqmSummary` / `ProvenanceRecord` / `AuditRef`
# now live above `JobResult` (TMX-SEAM-WIRE) so the live `/result` route can
# carry them without a forward reference. `SegmentResult` / `JobResultResponse`
# below still compose those shared models; neither is wired to a route yet —
# a future loop composes them into a per-segment / v2 result route.
# ---------------------------------------------------------------------------

class SegmentResult(BaseModel):
    """One segment's disposition, MQM summary, provenance and audit pointer."""
    segment_id: str
    disposition: TranslationDisposition
    mqm: MqmSummary
    provenance: ProvenanceRecord
    audit: AuditRef
    contract_version: str = CONTRACT_VERSION


class JobResultResponse(BaseModel):
    """ADR-0009 clause 3 result block, job-level. Not yet wired to a route —
    `JobResult` above remains the live `/result` response shape this loop;
    this is the additive shape a future v2 (or JobResult extension) composes.
    """
    job_id: str
    disposition: TranslationDisposition
    segments: List[SegmentResult] = Field(default_factory=list)
    audit: AuditRef
    contract_version: str = CONTRACT_VERSION


def tm_match_key(hash_canonical: str, target_locale: str, termbase_version_id: str) -> str:
    """ADR-0009 clause 4 — the TM match key, adopted verbatim from reSCApe's
    draft architecture note: `(source_component_version.hash_canonical,
    target_locale, termbase_version_id)`.

    Keying on the content hash gives reuse across components; including the
    termbase version means a terminology change invalidates the match
    automatically (bind-revalidation) rather than relying on a policy someone
    must remember to enforce. A bound segment still runs the deterministic
    gates — binding skips the model, never the checks (ADR-0009 clause 4,
    C-5) — but that lookup/skip logic is out of scope for this ticket; this
    function only derives the key.

    Mirrors the canonical-JSON + sha256 pattern already used for stable
    identifiers in this codebase (see
    `app.core.metric_profiles.registry._compute_hash`) rather than raw
    delimiter concatenation.
    """
    payload = json.dumps(
        {
            "hash_canonical": hash_canonical,
            "target_locale": target_locale,
            "termbase_version_id": termbase_version_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

