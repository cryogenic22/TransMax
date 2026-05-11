"""
TMX-3104 — Audit Ledger v2 independent re-compute verifier.

The audit chain's claim of tamper-evidence is only as strong as a verifier
that can re-prove it. A writer-only world is theatre: the writer can re-emit
its own bytes and call them verified. This module ships an INDEPENDENT
re-implementation of the canonical algorithm, byte-for-byte agreement
between writer (``app/services/audit_writer_v2.py``) and this verifier IS
the spec verification.

Shared canon
============

The constants ``DOMAIN_TAG`` and ``GENESIS_HASH`` are pulled from
``app/services/_audit_canonical.py``. The constants ARE the spec. The
HASH FUNCTIONS, however, are INDEPENDENT re-implementations — they MUST
NOT import the writer's ``compute_payload_hash`` / ``compute_event_hash``.
Two independent implementations agreeing byte-for-byte is the verification.

Per-event findings
==================

``EventFinding`` enum + ``EventReport`` dataclass + ``VerificationReport``
dataclass — see worksheet stage 3 for cascade semantics across the seven
finding classes.

API
===

::

    verifier = AuditVerifierV2(session_factory=SessionLocal)

    # Verify one job's chain
    report = verifier.verify_job_chain(job_id)
    assert report.is_valid

    # Verify all chains for current org (or specific org)
    reports = verifier.verify_org_chain()                       # current
    reports = verifier.verify_org_chain(organization_id=org_id) # explicit

    # Pure helpers (no DB) — useful for external re-verification
    payload_hash = AuditVerifierV2.recompute_payload_hash({"foo": "bar"})
    event_hash = AuditVerifierV2.recompute_event_hash(seq=0, prev_hash=GENESIS, payload_hash=payload_hash)

Addenda
-------

* **A1** — verifier is regulator-facing; TMX-3104a will add a
  ``VERIFICATION_REQUESTED`` audit event on each invocation (deferred to
  keep this loop scoped).
* **A3** — fails loud. No silent skips on unparseable rows.
* **A4** — touches only v2 models. v1 audit untouched.
* **A6** — outputs structured evidence a regulator can re-verify.

Closes TMX-3104. Builds on TMX-3101 (writer at ``c531b5a``) +
TMX-3100 (schema at ``7022f49``).
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tenant_context import TenantContextMissing, current_org_id, org_context
from app.models.audit_v2 import AuditEventV2
from app.services._audit_canonical import DOMAIN_TAG, GENESIS_HASH

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class EventFinding(str, Enum):
    """A specific defect detected on one audit event.

    Order matters for stable output (alphabetical-by-name is incidental).
    """

    OK = "ok"
    TAMPERED_PAYLOAD = "tampered_payload"
    """``stored payload_hash != SHA-256(canonical_json(stored payload))``.

    The most common attack class: someone mutated the JSON payload but did
    not re-derive the hash. Chain hashes still walk because event_hash
    binds to payload_hash, not to payload directly. The defect surfaces
    here: stored payload no longer matches its claimed hash.
    """

    TAMPERED_EVENT_HASH = "tampered_event_hash"
    """``stored event_hash != SHA-256(DOMAIN_TAG || seq || stored prev_hash || stored payload_hash)``.

    Someone mutated the event_hash column (or mutated previous_hash, which
    causes the same recompute mismatch when the spec uses stored prev_hash
    + stored payload_hash). In the prev-hash-mutation case, BROKEN_CHAIN
    also fires.
    """

    BROKEN_CHAIN = "broken_chain"
    """``event.previous_hash != prior event's event_hash``.

    The stored chain doesn't link. Either the previous_hash column was
    tampered, or an upstream event was deleted/replaced.
    """

    SEQUENCE_GAP = "sequence_gap"
    """A ``sequence_index`` was skipped (e.g. 0, 1, 3 — missing 2).

    Implies an event was deleted. Often co-occurs with BROKEN_CHAIN on the
    event that follows the gap.
    """

    SEQUENCE_DUPLICATE = "sequence_duplicate"
    """Two events at the same ``sequence_index``.

    DB ``UNIQUE(job_id, sequence_index)`` constraint should prevent this;
    surfaced defensively in case the constraint is bypassed (e.g. direct
    SQL INSERT against a permissive backend).
    """

    INVALID_HASH_LENGTH = "invalid_hash_length"
    """One of ``payload_hash`` / ``previous_hash`` / ``event_hash`` is not
    exactly 32 bytes.

    Schema CHECK constraint should prevent this; surfaced defensively in
    case the constraint is bypassed (e.g. SQLite without enforced CHECK).
    """

    GENESIS_VIOLATION = "genesis_violation"
    """``sequence_index == 0`` but ``previous_hash != GENESIS_HASH``.

    The genesis event MUST have ``previous_hash = b"\\x00" * 32``. Any
    other value is a fabrication.
    """


@dataclass(frozen=True)
class EventReport:
    """One finding on one audit event.

    OK findings are NOT emitted — absence of an EventReport for an event
    means the verifier finds no defect on that event.
    """

    event_id: str
    sequence_index: int
    finding: EventFinding
    detail: str | None = None


@dataclass(frozen=True)
class VerificationReport:
    """The full report for one job (or one whole-org verification request).

    ``is_valid`` is true iff ``findings`` is empty. Empty-chain jobs (zero
    events) are valid by construction — there's nothing to verify, so the
    chain has nothing to fail at.
    """

    organization_id: str
    job_id: str | None
    event_count: int
    ok_count: int
    findings: list[EventReport] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.findings) == 0


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------


class AuditVerifierV2:
    """Independent re-compute verifier for the v2 audit chain.

    Public methods:

    - :py:meth:`verify_job_chain` — verify one job's chain.
    - :py:meth:`verify_org_chain` — verify every chain for an org.
    - :py:meth:`verify_event` — verify one event (with optional expected
      prev_hash for chain-linkage check).
    - :py:meth:`recompute_payload_hash` — independent re-implementation
      of the canonical payload-hash algorithm.
    - :py:meth:`recompute_event_hash` — independent re-implementation
      of the canonical event-hash algorithm.

    The ``recompute_*`` static methods MUST NOT call into the writer's
    ``compute_*`` methods. They are deliberate, independent witnesses of
    the same spec. See worksheet stage 3 for rationale.
    """

    DOMAIN_TAG: bytes = DOMAIN_TAG
    """18-byte domain tag (17 ASCII characters + 1 NUL terminator). Pulled from
    ``_audit_canonical``. Equals the writer's :py:attr:`AuditWriterV2.DOMAIN_TAG`."""

    GENESIS_HASH: bytes = GENESIS_HASH
    """32-byte zero sentinel for genesis events. Pulled from
    ``_audit_canonical``. Equals the writer's
    :py:attr:`AuditWriterV2.GENESIS_HASH`."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        """
        Args:
            session_factory: zero-arg callable returning a fresh SQLAlchemy
                ``Session``. Typically ``app.core.database.SessionLocal``.
        """
        self._session_factory = session_factory

    # --- Pure helpers (independent re-implementations) ------------------

    @staticmethod
    def recompute_payload_hash(payload: dict[str, Any]) -> bytes:
        """Independent re-implementation of the canonical payload-hash algorithm.

        ::

            payload_hash = SHA-256(
                json.dumps(payload, sort_keys=True, separators=(',', ':'),
                           ensure_ascii=False, allow_nan=False)
                .encode('utf-8')
            )

        This is byte-equivalent to the writer's
        :py:meth:`AuditWriterV2.compute_payload_hash` BUT is a separately
        authored implementation. The two-implementation-agreement test
        (tests/test_audit_verifier_v2.py::test_two_implementation_agreement_...)
        is the byte-equality check.

        Returns:
            Exactly 32 bytes.

        Raises:
            ValueError: payload contains NaN/Infinity.
            TypeError:  payload contains non-JSON-serialisable objects.
        """
        # Independent canonicalisation — written from the spec, not copied.
        try:
            canonical_bytes = json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        except ValueError:
            # allow_nan=False raises ValueError on NaN/Infinity.
            raise ValueError(
                "Audit payload contains NaN or Infinity. Canonical JSON forbids "
                "these. Use a string sentinel or pre-validate the payload."
            )
        digest = hashlib.sha256()
        digest.update(canonical_bytes)
        return digest.digest()

    @staticmethod
    def recompute_event_hash(
        seq: int,
        prev_hash: bytes,
        payload_hash: bytes,
    ) -> bytes:
        """Independent re-implementation of the canonical event-hash algorithm.

        ::

            event_hash = SHA-256(
                DOMAIN_TAG                                          # 18 bytes
                || seq.to_bytes(8, 'little', signed=False)         #  8 bytes
                || prev_hash                                        # 32 bytes
                || payload_hash                                     # 32 bytes
            )                                                       # = 90 bytes preimage

        Args:
            seq: non-negative sequence index for this event.
            prev_hash: prior event's event_hash (or GENESIS_HASH for seq=0).
                Must be exactly 32 bytes.
            payload_hash: SHA-256 of canonical JSON. Must be exactly 32 bytes.

        Returns:
            Exactly 32 bytes.

        Raises:
            ValueError: any input malformed.
        """
        if seq < 0:
            raise ValueError(f"sequence_index must be >= 0, got {seq}")
        if not isinstance(prev_hash, bytes) or len(prev_hash) != 32:
            raise ValueError(
                f"prev_hash must be exactly 32 bytes, got "
                f"{type(prev_hash).__name__} of length "
                f"{len(prev_hash) if isinstance(prev_hash, bytes) else 'n/a'}"
            )
        if not isinstance(payload_hash, bytes) or len(payload_hash) != 32:
            raise ValueError(
                f"payload_hash must be exactly 32 bytes, got "
                f"{type(payload_hash).__name__} of length "
                f"{len(payload_hash) if isinstance(payload_hash, bytes) else 'n/a'}"
            )

        # Independent byte-concatenation — written from the spec, not copied.
        preimage = b"".join((
            DOMAIN_TAG,
            seq.to_bytes(8, "little", signed=False),
            prev_hash,
            payload_hash,
        ))
        return hashlib.sha256(preimage).digest()

    # --- Per-event verification -----------------------------------------

    def verify_event(
        self,
        event: AuditEventV2,
        expected_prev_hash: bytes | None,
    ) -> EventReport:
        """Verify a single audit event.

        Args:
            event: the stored event row.
            expected_prev_hash: the prior event's ``event_hash``, or
                :py:attr:`GENESIS_HASH` for ``seq == 0``. Pass ``None``
                to skip the chain-linkage check (e.g. standalone audits).

        Returns:
            An :py:class:`EventReport`. ``finding == OK`` and
            ``detail is None`` when no defect is detected.

        Note: when multiple defects co-occur on one event (e.g. both
        TAMPERED_EVENT_HASH and BROKEN_CHAIN), this method returns ONLY
        ONE finding (the highest-priority one in the order checked).
        Callers wanting all findings should use :py:meth:`verify_job_chain`.
        """
        # Hash-length defensive check (schema CHECK should prevent these).
        for col_name, value in (
            ("payload_hash", event.payload_hash),
            ("previous_hash", event.previous_hash),
            ("event_hash", event.event_hash),
        ):
            if not isinstance(value, (bytes, bytearray, memoryview)) or len(value) != 32:
                return EventReport(
                    event_id=str(event.event_id),
                    sequence_index=int(event.sequence_index),
                    finding=EventFinding.INVALID_HASH_LENGTH,
                    detail=f"{col_name} is {len(value) if hasattr(value, '__len__') else 'n/a'} bytes (need 32)",
                )

        stored_payload_hash = bytes(event.payload_hash)
        stored_prev_hash = bytes(event.previous_hash)
        stored_event_hash = bytes(event.event_hash)
        seq = int(event.sequence_index)

        # Genesis check (only meaningful when seq == 0).
        if seq == 0 and stored_prev_hash != GENESIS_HASH:
            return EventReport(
                event_id=str(event.event_id),
                sequence_index=seq,
                finding=EventFinding.GENESIS_VIOLATION,
                detail=(
                    f"seq=0 must have previous_hash = GENESIS_HASH (32 zero bytes); "
                    f"got 0x{stored_prev_hash.hex()[:16]}..."
                ),
            )

        # Tampered payload — recompute payload_hash from stored payload.
        recomputed_payload_hash = self.recompute_payload_hash(event.payload)
        if recomputed_payload_hash != stored_payload_hash:
            return EventReport(
                event_id=str(event.event_id),
                sequence_index=seq,
                finding=EventFinding.TAMPERED_PAYLOAD,
                detail=(
                    f"stored payload_hash=0x{stored_payload_hash.hex()[:16]}... "
                    f"recomputed=0x{recomputed_payload_hash.hex()[:16]}..."
                ),
            )

        # Tampered event_hash — recompute event_hash from STORED prev_hash +
        # STORED payload_hash. Using stored (not recomputed) on inputs lets us
        # isolate "did someone mutate event_hash itself?" from "did someone
        # mutate the inputs?".
        recomputed_event_hash = self.recompute_event_hash(
            seq, stored_prev_hash, stored_payload_hash
        )
        if recomputed_event_hash != stored_event_hash:
            return EventReport(
                event_id=str(event.event_id),
                sequence_index=seq,
                finding=EventFinding.TAMPERED_EVENT_HASH,
                detail=(
                    f"stored event_hash=0x{stored_event_hash.hex()[:16]}... "
                    f"recomputed=0x{recomputed_event_hash.hex()[:16]}..."
                ),
            )

        # Chain linkage — only if caller supplied an expected_prev_hash.
        if expected_prev_hash is not None and stored_prev_hash != expected_prev_hash:
            return EventReport(
                event_id=str(event.event_id),
                sequence_index=seq,
                finding=EventFinding.BROKEN_CHAIN,
                detail=(
                    f"stored previous_hash=0x{stored_prev_hash.hex()[:16]}... "
                    f"expected=0x{expected_prev_hash.hex()[:16]}..."
                ),
            )

        return EventReport(
            event_id=str(event.event_id),
            sequence_index=seq,
            finding=EventFinding.OK,
            detail=None,
        )

    # --- Chain verification ---------------------------------------------

    def verify_job_chain(self, job_id: str) -> VerificationReport:
        """Verify the full chain of audit events for one job.

        Emits ALL detected findings per event (not just the first). For
        example, mutating ``previous_hash`` produces BOTH
        ``TAMPERED_EVENT_HASH`` and ``BROKEN_CHAIN`` on the affected event —
        see worksheet stage 3 cascade analysis.

        Tenancy: TenantScopedMixin auto-filters by current org. Callers must
        be inside an ``org_context`` or this will raise upstream.

        Args:
            job_id: the FK to ``translation_jobs.id``.

        Returns:
            A :py:class:`VerificationReport`.

        Raises:
            TenantContextMissing: no org_context is active.
        """
        org_id = current_org_id()
        if org_id is None:
            raise TenantContextMissing(
                "AuditVerifierV2.verify_job_chain requires a tenant context. "
                "Wrap the call in `org_context(org_id)`."
            )

        session = self._session_factory()
        try:
            stmt = (
                select(AuditEventV2)
                .where(AuditEventV2.job_id == job_id)
                .order_by(AuditEventV2.sequence_index.asc())
            )
            events = list(session.execute(stmt).scalars().all())
        finally:
            session.close()

        return self._verify_event_sequence(
            events=events,
            organization_id=org_id,
            job_id=job_id,
        )

    def verify_org_chain(
        self,
        organization_id: str | None = None,
    ) -> list[VerificationReport]:
        """Verify every job's chain for an organisation.

        Args:
            organization_id: explicit org id. If ``None``, reads from
                :py:func:`current_org_id`. If both None, raises
                :py:class:`TenantContextMissing` (A3).

        Returns:
            One :py:class:`VerificationReport` per distinct ``job_id`` in
            the org's audit_events_v2. Empty list if the org has no events.

        Raises:
            TenantContextMissing: if neither explicit org nor context.
        """
        if organization_id is None:
            organization_id = current_org_id()
        if organization_id is None:
            raise TenantContextMissing(
                "AuditVerifierV2.verify_org_chain requires either an explicit "
                "organization_id or an active org_context."
            )

        # Use org_context to make TenantScopedMixin filters apply when we
        # query for distinct job_ids. Nested context is fine — restores
        # whatever was set before.
        with org_context(organization_id):
            session = self._session_factory()
            try:
                stmt = (
                    select(AuditEventV2.job_id)
                    .distinct()
                )
                job_ids = [str(jid) for (jid,) in session.execute(stmt).all()]
            finally:
                session.close()

            return [self.verify_job_chain(jid) for jid in job_ids]

    # --- Internal: walk an ordered event list ---------------------------

    def _verify_event_sequence(
        self,
        *,
        events: list[AuditEventV2],
        organization_id: str,
        job_id: str | None,
    ) -> VerificationReport:
        """Walk a pre-fetched, seq-ascending list of events and collect findings.

        Per-event we emit AT MOST the following independent findings:
        - INVALID_HASH_LENGTH (terminal for this event — can't proceed safely)
        - GENESIS_VIOLATION (only seq=0)
        - TAMPERED_PAYLOAD (stored payload no longer matches stored hash)
        - TAMPERED_EVENT_HASH (stored event_hash != recomputed)
        - BROKEN_CHAIN (stored prev != prior stored event_hash)
        - SEQUENCE_GAP / SEQUENCE_DUPLICATE (relative to expected_seq)

        Multiple findings on the same event are all emitted as separate
        :py:class:`EventReport` entries — the verifier reports every
        defect it sees, not just the first.
        """
        findings: list[EventReport] = []
        expected_seq = 0
        expected_prev: bytes | None = GENESIS_HASH
        ok_count = 0

        for event in events:
            seq = int(event.sequence_index)
            event_id_str = str(event.event_id)
            this_event_findings: list[EventReport] = []

            # --- Sequence checks ---
            if seq > expected_seq:
                this_event_findings.append(EventReport(
                    event_id=event_id_str,
                    sequence_index=seq,
                    finding=EventFinding.SEQUENCE_GAP,
                    detail=f"expected seq={expected_seq}, got seq={seq}",
                ))
                expected_seq = seq
            elif seq < expected_seq:
                this_event_findings.append(EventReport(
                    event_id=event_id_str,
                    sequence_index=seq,
                    finding=EventFinding.SEQUENCE_DUPLICATE,
                    detail=f"expected seq={expected_seq}, got seq={seq} (duplicate or out-of-order)",
                ))
                # Do not advance expected_seq; the duplicate doesn't replace the slot.

            # --- Hash-length defensive check ---
            invalid_length_found = False
            for col_name, value in (
                ("payload_hash", event.payload_hash),
                ("previous_hash", event.previous_hash),
                ("event_hash", event.event_hash),
            ):
                if not isinstance(value, (bytes, bytearray, memoryview)) or len(value) != 32:
                    this_event_findings.append(EventReport(
                        event_id=event_id_str,
                        sequence_index=seq,
                        finding=EventFinding.INVALID_HASH_LENGTH,
                        detail=f"{col_name} is {len(value) if hasattr(value, '__len__') else 'n/a'} bytes (need 32)",
                    ))
                    invalid_length_found = True
                    break

            if invalid_length_found:
                # Can't safely proceed with hash recomputation on this event.
                # Advance expected_seq + chain state to the next slot but
                # treat this row's hashes as unknown.
                expected_seq = seq + 1
                expected_prev = None  # next event's chain check is moot
                findings.extend(this_event_findings)
                continue

            stored_payload_hash = bytes(event.payload_hash)
            stored_prev_hash = bytes(event.previous_hash)
            stored_event_hash = bytes(event.event_hash)

            # --- Genesis violation (mutually exclusive with chain-linkage on seq=0) ---
            if seq == 0 and stored_prev_hash != GENESIS_HASH:
                this_event_findings.append(EventReport(
                    event_id=event_id_str,
                    sequence_index=seq,
                    finding=EventFinding.GENESIS_VIOLATION,
                    detail=(
                        f"seq=0 must have previous_hash = GENESIS_HASH (32 zero bytes); "
                        f"got 0x{stored_prev_hash.hex()[:16]}..."
                    ),
                ))

            # --- Tampered payload ---
            try:
                recomputed_payload_hash = self.recompute_payload_hash(event.payload)
            except (ValueError, TypeError) as exc:
                # A3 — fail loud as a finding, not a crash.
                this_event_findings.append(EventReport(
                    event_id=event_id_str,
                    sequence_index=seq,
                    finding=EventFinding.TAMPERED_PAYLOAD,
                    detail=f"payload could not be canonicalised: {exc}",
                ))
                recomputed_payload_hash = None  # signal we can't trust downstream recompute

            if recomputed_payload_hash is not None and recomputed_payload_hash != stored_payload_hash:
                this_event_findings.append(EventReport(
                    event_id=event_id_str,
                    sequence_index=seq,
                    finding=EventFinding.TAMPERED_PAYLOAD,
                    detail=(
                        f"stored payload_hash=0x{stored_payload_hash.hex()[:16]}... "
                        f"recomputed=0x{recomputed_payload_hash.hex()[:16]}..."
                    ),
                ))

            # --- Tampered event_hash ---
            # Use STORED payload_hash + STORED prev_hash for recompute so that
            # this check is independent of TAMPERED_PAYLOAD.
            recomputed_event_hash = self.recompute_event_hash(
                seq, stored_prev_hash, stored_payload_hash
            )
            if recomputed_event_hash != stored_event_hash:
                this_event_findings.append(EventReport(
                    event_id=event_id_str,
                    sequence_index=seq,
                    finding=EventFinding.TAMPERED_EVENT_HASH,
                    detail=(
                        f"stored event_hash=0x{stored_event_hash.hex()[:16]}... "
                        f"recomputed=0x{recomputed_event_hash.hex()[:16]}..."
                    ),
                ))

            # --- Broken chain (skip on seq=0; that's the genesis-violation case) ---
            if (
                seq > 0
                and expected_prev is not None
                and stored_prev_hash != expected_prev
            ):
                this_event_findings.append(EventReport(
                    event_id=event_id_str,
                    sequence_index=seq,
                    finding=EventFinding.BROKEN_CHAIN,
                    detail=(
                        f"stored previous_hash=0x{stored_prev_hash.hex()[:16]}... "
                        f"expected (prior event's event_hash)=0x{expected_prev.hex()[:16]}..."
                    ),
                ))

            # --- Advance walker state ---
            if not this_event_findings:
                ok_count += 1
            findings.extend(this_event_findings)
            expected_seq = seq + 1
            expected_prev = stored_event_hash  # walk on the STORED chain

        return VerificationReport(
            organization_id=organization_id,
            job_id=job_id,
            event_count=len(events),
            ok_count=ok_count,
            findings=findings,
        )
