"""
TMX-3101 — Audit Ledger v2 writer (canonical chained-hash algorithm).

This module is the v3.0 regulator-defensible audit writer. It supersedes the
v1 writer in `app/services/audit_service.py` (which has the C-04 weakness:
hardcoded `"GENESIS_HASH"` string seed + string-concatenation hashing without
domain separator). v1 stays in place as compat for non-migrated callers;
TMX-3110 swaps callers ticket-by-ticket.

CANONICAL ALGORITHM (the spec — load-bearing, byte-exact)
=========================================================

Constants
---------

::

    DOMAIN_TAG    = b"transmax.audit.v1\\0"   # 20 bytes; NUL-terminated UTF-8
    GENESIS_HASH  = b"\\x00" * 32              # 32 zero bytes (well-defined
                                              # sentinel; NOT the v1 string).

Canonical JSON
--------------

::

    canonical_json(payload: dict) -> bytes:
        return json.dumps(
            payload,
            sort_keys=True,           # deterministic key ordering
            separators=(',', ':'),    # no whitespace
            ensure_ascii=False,       # raw UTF-8 codepoints
            allow_nan=False,          # reject NaN/Infinity (cross-language hazard)
        ).encode('utf-8')

Pinned choices:

* ``sort_keys=True`` — deterministic across writers + verifiers.
* ``separators=(',', ':')`` — no whitespace.
* ``ensure_ascii=False`` — emit raw UTF-8 codepoints (e.g. ``é`` not ``\\u00e9``).
* ``allow_nan=False`` — Python's default emits ``NaN``/``Infinity`` which are
  NOT valid JSON; reject at the writer.
* **Floats**: Python's ``json.dumps`` uses ``repr(float)``. Cross-language
  verifiers may emit different reprs. Callers SHOULD use strings or ints
  for numerics where byte-exactness matters.
* **Unicode normalisation**: NOT applied. ``"é"`` (U+00E9, 1 codepoint) and
  ``"é"`` (U+0065 U+0301, 2 codepoints) hash differently. Callers who want
  normalised input must NFC-normalise before passing.

Hash construction
-----------------

::

    payload_hash = SHA-256(canonical_json(payload))         # 32 bytes

    event_hash   = SHA-256(
        DOMAIN_TAG                                           # 20 bytes
        || sequence_index.to_bytes(8, 'little', signed=False) #  8 bytes
        || previous_hash                                     # 32 bytes
        || payload_hash                                      # 32 bytes
    )                                                        # 32 bytes

Total preimage = 20 + 8 + 32 + 32 = **92 bytes** of fixed-width input. No
length-prefix needed — every component is fixed-width and the variable-
length JSON payload is hashed first into a fixed-width digest.

Genesis: ``sequence_index == 0`` ⇒ ``previous_hash = GENESIS_HASH``.
The all-zero pattern is detectable AND domain-separates from any real
SHA-256 output (probability 2^-256, cryptographically impossible to collide).

Concurrency
-----------

The ``(job_id, sequence_index)`` UNIQUE constraint guarantees no two events
share a sequence. Concurrent writers for the same job MAY collide on
``seq=N``. Strategy: ``BEGIN`` + read-max + write + on ``IntegrityError``,
re-read max+1, recompute hash, retry up to N=5 attempts. Beyond N, raise.

This works on both SQLite (test env) and Postgres (prod). Future:
TMX-3101a may add Postgres advisory-lock for high-concurrency-per-job paths.

Addenda
-------

* **A1** — this IS the audit infrastructure. Writer never bypasses other audit signals.
* **A3** — failures propagate. No fallback to v1, no swallow-and-log, no placeholder hash.
* **A4** — touches only ``audit_v2.py``. Never reaches into v1 models.
* **A6** — payload-shape-agnostic; callers can pin model_version / prompt_version /
  token_usage in payload (qualified-supplier evidence).

Closes review finding C-04. Ships TMX-3101.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.tenant_context import TenantContextMissing, current_org_id
from app.models.audit_v2 import AuditEventV2

logger = logging.getLogger(__name__)


_VALID_ACTOR_KINDS = ("user", "system", "agent")
ActorKind = Literal["user", "system", "agent"]


class AuditWriterV2:
    """Canonical chained-hash writer for the v2 audit ledger.

    Public API:

    - :py:attr:`DOMAIN_TAG` — the 20-byte canonical domain tag (NUL-terminated).
    - :py:attr:`GENESIS_HASH` — the 32-byte zero sentinel for genesis events.
    - :py:meth:`record_event` — append an event to the chain.
    - :py:meth:`compute_payload_hash` — pure helper; canonical JSON + SHA-256.
    - :py:meth:`compute_event_hash` — pure helper; the canonical hash construction.

    The two ``compute_*`` static methods exist so an external verifier
    (TMX-3104) can re-implement the algorithm in any language and confirm
    byte-exact match against stored events. They are deliberately
    side-effect-free and DB-free.
    """

    # --- Canonical algorithm constants (the spec) -----------------------

    DOMAIN_TAG: bytes = b"transmax.audit.v1\0"
    """20-byte domain tag. NUL-terminator is part of the tag (domain separator
    vs. any future tag without trailing NUL)."""

    GENESIS_HASH: bytes = b"\x00" * 32
    """32-byte zero sentinel used as ``previous_hash`` for ``sequence_index == 0``.

    Closes C-04: the v1 writer used the literal string ``"GENESIS_HASH"``
    which made the genesis hash a 13-byte ASCII string while every other
    chain entry was a 64-char hex digest — a textbook domain-separation bug.
    """

    _MAX_INTEGRITY_RETRIES: int = 5
    """Maximum retries on UNIQUE(job_id, sequence_index) collision before
    giving up. See concurrency note in the module docstring."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        """
        Args:
            session_factory: zero-arg callable returning a fresh SQLAlchemy
                ``Session``. Typically ``app.core.database.SessionLocal``.
        """
        self._session_factory = session_factory

    # --- Pure helpers (no DB, no I/O) -----------------------------------

    @staticmethod
    def compute_payload_hash(payload: dict[str, Any]) -> bytes:
        """SHA-256 of the canonical-JSON encoding of ``payload``.

        Returns:
            Exactly 32 bytes.

        Raises:
            ValueError: if ``payload`` contains NaN/Infinity (allow_nan=False).
            TypeError:  if ``payload`` contains non-JSON-serialisable objects.
        """
        try:
            canonical = json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        except ValueError:
            # allow_nan=False raises ValueError on NaN/Infinity. Re-raise
            # as a clearer ValueError for callers; A3 — never silently substitute.
            raise ValueError(
                "Payload contains NaN or Infinity. Canonical JSON forbids these. "
                "Use a string sentinel or pre-validate."
            )
        return hashlib.sha256(canonical).digest()

    @staticmethod
    def compute_event_hash(
        seq: int,
        prev_hash: bytes,
        payload_hash: bytes,
    ) -> bytes:
        """Canonical event-hash construction.

        ::

            event_hash = SHA-256(
                DOMAIN_TAG               # 20 bytes
                || seq.to_bytes(8, 'little', signed=False)  # 8 bytes
                || prev_hash             # 32 bytes
                || payload_hash          # 32 bytes
            )

        Args:
            seq: non-negative ``sequence_index`` for this event.
            prev_hash: prior event's ``event_hash`` (or ``GENESIS_HASH`` for seq=0).
                Must be exactly 32 bytes.
            payload_hash: SHA-256 of canonical JSON. Must be exactly 32 bytes.

        Returns:
            Exactly 32 bytes.

        Raises:
            ValueError: if any input is malformed.
        """
        if seq < 0:
            raise ValueError(f"sequence_index must be >= 0, got {seq}")
        if not isinstance(prev_hash, bytes) or len(prev_hash) != 32:
            raise ValueError(
                f"prev_hash must be exactly 32 bytes, got {type(prev_hash).__name__} "
                f"of length {len(prev_hash) if isinstance(prev_hash, bytes) else 'n/a'}"
            )
        if not isinstance(payload_hash, bytes) or len(payload_hash) != 32:
            raise ValueError(
                f"payload_hash must be exactly 32 bytes, got "
                f"{type(payload_hash).__name__} of length "
                f"{len(payload_hash) if isinstance(payload_hash, bytes) else 'n/a'}"
            )
        h = hashlib.sha256()
        h.update(AuditWriterV2.DOMAIN_TAG)
        h.update(seq.to_bytes(8, "little", signed=False))
        h.update(prev_hash)
        h.update(payload_hash)
        return h.digest()

    # --- The append operation -------------------------------------------

    def record_event(
        self,
        *,
        job_id: str,
        event_type: str,
        actor_id: str | None,
        actor_kind: ActorKind,
        payload: dict[str, Any],
    ) -> AuditEventV2:
        """Append an event to the v2 audit chain for ``job_id``.

        Resolves ``organization_id`` from the current tenant context, computes
        ``sequence_index`` and ``previous_hash`` from the prior event, then
        canonical-hashes and inserts. Retries on UNIQUE collisions up to
        :py:attr:`_MAX_INTEGRITY_RETRIES` attempts.

        Args:
            job_id: FK to ``translation_jobs.id``.
            event_type: non-empty event-type identifier (e.g. ``JOB_STARTED``).
            actor_id: FK to a user / agent / system identity. May be None
                for system-actor events not tied to a user.
            actor_kind: one of ``user``, ``system``, ``agent``.
            payload: JSON-serialisable dict. Must not contain NaN/Infinity.

        Returns:
            The persisted ``AuditEventV2`` instance.

        Raises:
            TenantContextMissing: if no ``org_context`` is active.
            ValueError: if ``event_type`` is empty, ``actor_kind`` is invalid,
                or the payload contains NaN/Infinity.
            IntegrityError: if all retries exhausted under contention. (Caller
                should NOT swallow — A3 says fail loud.)
        """
        # --- input validation (fail loud per A3) ---
        if not event_type:
            raise ValueError("event_type must be a non-empty string")
        if actor_kind not in _VALID_ACTOR_KINDS:
            raise ValueError(
                f"actor_kind must be one of {_VALID_ACTOR_KINDS!r}, got {actor_kind!r}"
            )

        # Resolve tenant. The mixin would also raise on insert, but failing
        # early gives a cleaner error before we burn a payload_hash compute.
        org_id = current_org_id()
        if org_id is None:
            raise TenantContextMissing(
                "AuditWriterV2.record_event requires a tenant context. "
                "Wrap the work in `org_context(org_id)` or use "
                "`get_db_session(tenant_id=...)`."
            )

        # Compute payload_hash once; it doesn't depend on the prev_hash, so
        # it survives retries unchanged. Raises ValueError on NaN/Infinity.
        payload_hash = self.compute_payload_hash(payload)

        last_exc: Exception | None = None
        for attempt in range(self._MAX_INTEGRITY_RETRIES):
            session = self._session_factory()
            try:
                # Read max(sequence_index) for this job; compute next.
                last_event = (
                    session.query(AuditEventV2)
                    .filter(AuditEventV2.job_id == job_id)
                    .order_by(desc(AuditEventV2.sequence_index))
                    .first()
                )
                if last_event is None:
                    seq: int = 0
                    prev_hash: bytes = self.GENESIS_HASH
                else:
                    seq = int(last_event.sequence_index) + 1
                    prev_hash = bytes(last_event.event_hash)
                    if len(prev_hash) != 32:
                        # Schema CHECK should make this unreachable; defensive.
                        raise RuntimeError(
                            f"Stored event_hash for seq={last_event.sequence_index} "
                            f"is not 32 bytes — chain corrupt."
                        )

                event_hash = self.compute_event_hash(seq, prev_hash, payload_hash)

                event = AuditEventV2(
                    event_id=str(uuid.uuid4()),
                    organization_id=org_id,
                    job_id=job_id,
                    sequence_index=seq,
                    domain_tag=self.DOMAIN_TAG.decode("utf-8").rstrip("\x00"),
                    event_type=event_type,
                    actor_id=actor_id,
                    actor_kind=actor_kind,
                    payload=payload,
                    payload_hash=payload_hash,
                    previous_hash=prev_hash,
                    event_hash=event_hash,
                    event_ts_utc=datetime.now(timezone.utc),
                )
                session.add(event)
                session.commit()

                # Re-attach to a detached state for caller use; refresh pulls
                # any DB-side defaults (created_at).
                session.refresh(event)
                # Expunge so caller can use the instance after this method
                # returns and the session closes.
                session.expunge(event)
                return event

            except IntegrityError as exc:
                last_exc = exc
                session.rollback()
                logger.warning(
                    "AuditWriterV2: UNIQUE collision on (job_id=%s, seq=%s) "
                    "attempt %d/%d — retrying",
                    job_id, seq, attempt + 1, self._MAX_INTEGRITY_RETRIES,
                )
                continue
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        # Exhausted retries — A3: fail loud.
        assert last_exc is not None  # for type-checker
        raise last_exc
