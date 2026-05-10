"""
TMX-3107 — Daily Merkle anchor builder + pluggable object-store backend.

This module is the v3.0 daily-immutability primitive. Every day, for every
organisation, we:

  1. SELECT all ``AuditEventV2`` rows whose ``event_ts_utc`` falls in the
     half-open UTC interval ``[anchor_date 00:00:00, anchor_date+1 00:00:00)``,
     sorted by ``(event_ts_utc, sequence_index, event_id)``.
  2. Compute a domain-separated Merkle root over their ``event_hash`` values.
  3. Build a canonical-JSON manifest (org_id, date, root, event_hashes, etc.).
  4. Upload (manifest, root_bytes) to a pluggable ``AnchorObjectStore``
     (local filesystem in dev/test; S3 with Object Lock in prod via
     TMX-3107a).
  5. INSERT an ``AuditAnchor`` row carrying the URI + retention metadata.

The output is a regulator-defensible roll-up of the day's audit chain:
the manifest is the authoritative immutable record (immutability comes
from S3 Object Lock retention); the Merkle root in the DB matches the
``merkle_root`` field in the manifest; and an independent verifier with
the same set of events MUST compute the same root, byte-for-byte.

CANONICAL ALGORITHM (the spec — load-bearing, byte-exact)
=========================================================

Constants
---------

::

    LEAF_PREFIX     = b"\\x01"          # domain separator for leaves
    INTERNAL_PREFIX = b"\\x02"          # domain separator for internal nodes
    EMPTY_ROOT      = b"\\x00" * 32     # 32-byte zero sentinel; legitimate
                                         # for orgs with no activity that day
    ALGORITHM_ID    = "transmax.merkle.v1"

Merkle construction
-------------------

For a sorted list of 32-byte ``event_hashes`` ``[h_0, h_1, ..., h_{n-1}]``::

    if n == 0:        merkle_root = b"\\x00" * 32
    if n == 1:        merkle_root = SHA-256(b"\\x01" || h_0)
    if n >= 2:
        leaves = [SHA-256(b"\\x01" || h_i) for h_i in event_hashes]
        level  = leaves
        while len(level) > 1:
            next_level = []
            for i in range(0, len(level), 2):
                left  = level[i]
                right = level[i + 1] if i + 1 < len(level) else level[i]
                next_level.append(SHA-256(b"\\x02" || left || right))
            level = next_level
        merkle_root = level[0]

**Domain separation**: leaves prefixed with ``0x01``; internal nodes with
``0x02``. This prevents second-preimage attacks where an attacker could
substitute a leaf preimage for an internal node with matching content.
Standard Merkle hardening; matches RFC 6962 (Certificate Transparency).

**Odd levels**: duplicate the last node. Same approach as Bitcoin /
RFC 6962. The classic CVE-2012-2459 attack (force-feeding duplicate
leaves) doesn't apply here because (a) the manifest pins
``event_count`` authoritatively and (b) ``event_hash`` values are
chained — an attacker cannot cheaply forge a leaf that lands in the
duplicate slot.

Sort order (load-bearing)
-------------------------

Events MUST be sorted by ``(event_ts_utc, sequence_index, event_id)``
ascending. Any independent verifier MUST reproduce this exact order
or compute a different root. ``event_id`` is a UUID and breaks any
remaining ties.

Day boundary (UTC, half-open)
-----------------------------

The interval is ``[anchor_date 00:00:00 UTC, anchor_date+1 00:00:00 UTC)``.
Events at exactly ``00:00:00`` belong to the LATER day's anchor. UTC
is mandatory — local-time anchors would depend on the deployment's
clock zone and DST boundaries (creating 23-hour or 25-hour days),
which is unacceptable for a regulatory primitive.

Manifest (canonical JSON)
-------------------------

::

    {
      "algorithm":      "transmax.merkle.v1",
      "anchor_date":    "<YYYY-MM-DD>",
      "created_at":     "<ISO-8601 UTC>",
      "event_count":    <int>,
      "event_hashes":   ["<hex>", "<hex>", ...],   # in sort order
      "first_event_id": "<uuid>" | null,
      "last_event_id":  "<uuid>" | null,
      "merkle_root":    "<hex>",
      "org_id":         "<uuid>"
    }

Serialised with ``json.dumps(sort_keys=True, separators=(',', ':'),
ensure_ascii=False, allow_nan=False)`` and UTF-8 encoded — same flags
as TMX-3101's payload canonicalisation. ``sort_keys=True`` guarantees
field ordering is alphabetical regardless of insertion order.

**Empty-day manifest**: ``event_count=0``, ``event_hashes=[]``,
``first_event_id=None``, ``last_event_id=None``,
``merkle_root="00...00"``. This is a positive assertion that no events
occurred (A3 — never substitute a placeholder for missing data).

Object-store backend
--------------------

The manifest + root_bytes are uploaded to an ``AnchorObjectStore``
implementation:

  - ``LocalFilesystemObjectStore`` (default for dev/test): writes both
    artefacts to ``<root_dir>/<key>.{manifest.json,root.bin}``.
    Returns ``(file://<abs path>, None)``.
  - ``S3ObjectStore`` (stub; raises ``NotImplementedError``): TMX-3107a
    wires real boto3 + Object Lock retention
    (``ObjectLockMode='GOVERNANCE'``, ``RetainUntilDate=anchor_date+7yr``).

Idempotency
-----------

The ``audit_anchors`` UNIQUE constraint on ``(organization_id, anchor_date)``
ensures only one anchor per (org, day). ``build_anchor_for_day`` raises
``ValueError("already anchored")`` on the second call for the same key.
A3 forbids silently overwriting (immutability would be defeated); the
caller decides whether to delete the prior anchor (audit-logged) or skip.

Addenda
-------

* **A1** — anchor creation IS the audit roll-up signal. The recursive
  ``ANCHOR_BUILT`` event on the v2 chain is left to TMX-3107d (the
  scheduler) so the builder stays focused.
* **A3** — empty-day anchors are honest "no events" assertions; never
  silent fallbacks.
* **A4** — touches only ``audit_v2.py``. Never reaches into v1 models.
* **A6** — manifest is fully deterministic; no LLM in the path.

Closes audit 2026-05-09 §8 item 3 (daily Merkle anchor) and pairs with
TMX-3101 (the v2 audit writer at commit ``c531b5a``). Ships TMX-3107.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional, Protocol

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.tenant_context import TenantContextMissing, current_org_id
from app.models.audit_v2 import AuditAnchor, AuditEventV2

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Object-store backend
# ---------------------------------------------------------------------------


class AnchorObjectStore(Protocol):
    """Pluggable backend for anchor artefacts.

    Implementations MUST persist both the canonical manifest and the
    raw 32-byte Merkle root, and return a URI uniquely identifying the
    stored object plus an optional version id (where the backend
    supports versioning).

    Mirrors TMX-3052's ``CircuitBreakerStateStore`` pattern.
    """

    def put(
        self,
        *,
        key: str,
        manifest: bytes,
        root_bytes: bytes,
    ) -> tuple[str, Optional[str]]:
        """Persist (manifest, root_bytes) under ``key``.

        Returns:
            ``(s3_object_uri, version_id_or_None)``.
        """
        ...


class LocalFilesystemObjectStore:
    """Default backend — writes artefacts to a local directory.

    Intended for dev / test only. Real production MUST use S3 with
    Object Lock retention (TMX-3107a).

    Layout:
        ``<root_dir>/<key>.manifest.json``
        ``<root_dir>/<key>.root.bin``

    Files are written atomically (write to ``.tmp`` then rename) so a
    crashed half-write doesn't leave a corrupt manifest behind.
    """

    def __init__(self, root_dir: Path) -> None:
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)

    def put(
        self,
        *,
        key: str,
        manifest: bytes,
        root_bytes: bytes,
    ) -> tuple[str, Optional[str]]:
        if len(root_bytes) != 32:
            raise ValueError(
                f"root_bytes must be exactly 32 bytes, got {len(root_bytes)}"
            )

        manifest_path = self._root_dir / f"{key}.manifest.json"
        root_path = self._root_dir / f"{key}.root.bin"

        # Ensure parent dirs exist (key may contain a "/").
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write via tmp + rename.
        for path, data in ((manifest_path, manifest), (root_path, root_bytes)):
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)

        uri = manifest_path.resolve().as_uri()
        # Local fs has no version id concept.
        return uri, None


class S3ObjectStore:
    """Stub. TMX-3107a wires real boto3 + Object Lock retention.

    A3 (no silent fallbacks): when TMX-3107a lands, this class will
    raise loudly on misconfiguration (missing IAM perms, bucket not
    found, Object Lock not enabled) — never silently fall back to
    ``LocalFilesystemObjectStore``.
    """

    def put(
        self,
        *,
        key: str,
        manifest: bytes,
        root_bytes: bytes,
    ) -> tuple[str, Optional[str]]:
        raise NotImplementedError(
            "S3 backend wiring is TMX-3107a — boto3 dep + IAM policy + "
            "bucket creation + Object Lock retention policy required first."
        )


# ---------------------------------------------------------------------------
# Anchor builder
# ---------------------------------------------------------------------------


class AnchorBuilder:
    """Daily-Merkle-anchor builder for the v2 audit ledger.

    Public API:

    - :py:attr:`LEAF_PREFIX`     — ``b"\\x01"``; leaf-domain prefix.
    - :py:attr:`INTERNAL_PREFIX` — ``b"\\x02"``; internal-node prefix.
    - :py:attr:`EMPTY_ROOT`      — ``b"\\x00" * 32``; sentinel for empty days.
    - :py:attr:`ALGORITHM_ID`    — ``"transmax.merkle.v1"`` — pinned in the manifest.
    - :py:meth:`build_merkle_root` — pure helper (no DB, no I/O).
    - :py:meth:`build_manifest`    — pure helper; canonical JSON bytes.
    - :py:meth:`build_anchor_for_day` — the full SELECT → compute → upload → INSERT path.

    The static helpers exist so an external verifier can re-implement
    the algorithm in any language and confirm byte-exact match against
    stored manifests + anchor rows.
    """

    LEAF_PREFIX: bytes = b"\x01"
    INTERNAL_PREFIX: bytes = b"\x02"
    EMPTY_ROOT: bytes = b"\x00" * 32
    ALGORITHM_ID: str = "transmax.merkle.v1"

    def __init__(
        self,
        session_factory: Callable[[], Session],
        object_store: AnchorObjectStore,
    ) -> None:
        """
        Args:
            session_factory: zero-arg callable returning a fresh SQLAlchemy
                ``Session``. Typically ``app.core.database.SessionLocal``.
            object_store: the pluggable backend that persists manifests +
                root_bytes. Use ``LocalFilesystemObjectStore`` in dev/test;
                ``S3ObjectStore`` (post-TMX-3107a) in prod.
        """
        self._session_factory = session_factory
        self._object_store = object_store

    # --- Pure helpers (no DB, no I/O) -----------------------------------

    @staticmethod
    def build_merkle_root(event_hashes: list[bytes]) -> bytes:
        """Compute the canonical Merkle root over a sorted list of hashes.

        See module docstring for the full algorithm spec. This is a pure
        function — no DB, no I/O, fully deterministic.

        Args:
            event_hashes: sorted list of 32-byte event hashes. May be empty.

        Returns:
            Exactly 32 bytes. Returns ``EMPTY_ROOT`` (32 zero bytes) for
            an empty input list.

        Raises:
            ValueError: if any element is not exactly 32 bytes.
        """
        for i, h in enumerate(event_hashes):
            if not isinstance(h, bytes) or len(h) != 32:
                raise ValueError(
                    f"event_hashes[{i}] must be exactly 32 bytes, got "
                    f"{type(h).__name__} of length "
                    f"{len(h) if isinstance(h, bytes) else 'n/a'}"
                )

        n = len(event_hashes)
        if n == 0:
            return AnchorBuilder.EMPTY_ROOT
        if n == 1:
            return hashlib.sha256(AnchorBuilder.LEAF_PREFIX + event_hashes[0]).digest()

        level = [
            hashlib.sha256(AnchorBuilder.LEAF_PREFIX + h).digest()
            for h in event_hashes
        ]
        while len(level) > 1:
            next_level: list[bytes] = []
            for i in range(0, len(level), 2):
                left = level[i]
                right = level[i + 1] if i + 1 < len(level) else level[i]
                next_level.append(
                    hashlib.sha256(
                        AnchorBuilder.INTERNAL_PREFIX + left + right
                    ).digest()
                )
            level = next_level
        return level[0]

    @staticmethod
    def build_manifest(
        *,
        org_id: str,
        anchor_date: date,
        merkle_root: bytes,
        event_hashes: list[bytes],
        first_event_id: Optional[str],
        last_event_id: Optional[str],
        created_at: datetime,
    ) -> bytes:
        """Build the canonical-JSON manifest as UTF-8 bytes.

        See module docstring for the full canonical-JSON spec. Pure
        function — no DB, no I/O, fully deterministic.

        Args:
            org_id:          organisation UUID string.
            anchor_date:     ``date`` value for this anchor (UTC day).
            merkle_root:     32-byte root from :py:meth:`build_merkle_root`.
            event_hashes:    sorted list of 32-byte event hashes; must
                             match the input that produced ``merkle_root``.
            first_event_id:  UUID string of the first event in sort order,
                             or ``None`` for empty days.
            last_event_id:   UUID string of the last event in sort order,
                             or ``None`` for empty days.
            created_at:      timezone-aware UTC datetime of the build.

        Returns:
            Canonical-JSON-serialised manifest as UTF-8 bytes.

        Raises:
            ValueError: if ``merkle_root`` is not 32 bytes, or
                ``event_hashes`` and ``event_count`` disagree on emptiness.
        """
        if len(merkle_root) != 32:
            raise ValueError(
                f"merkle_root must be exactly 32 bytes, got {len(merkle_root)}"
            )
        if (len(event_hashes) == 0) != (
            first_event_id is None and last_event_id is None
        ):
            raise ValueError(
                "first_event_id / last_event_id MUST be None iff event_hashes is empty"
            )

        manifest = {
            "algorithm": AnchorBuilder.ALGORITHM_ID,
            "anchor_date": anchor_date.isoformat(),
            "created_at": created_at.isoformat(),
            "event_count": len(event_hashes),
            "event_hashes": [h.hex() for h in event_hashes],
            "first_event_id": first_event_id,
            "last_event_id": last_event_id,
            "merkle_root": merkle_root.hex(),
            "org_id": org_id,
        }
        return json.dumps(
            manifest,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")

    # --- The full daily-anchor build path -------------------------------

    def build_anchor_for_day(
        self,
        *,
        organization_id: str,
        anchor_date: date,
    ) -> AuditAnchor:
        """Compute and persist the Merkle anchor for one ``(org, date)`` pair.

        Steps:
          1. Resolve tenant context (raises if missing).
          2. SELECT events for this org with
             ``event_ts_utc IN [anchor_date 00:00 UTC, anchor_date+1 00:00 UTC)``,
             sorted by ``(event_ts_utc, sequence_index, event_id)``.
          3. Compute Merkle root over their ``event_hash`` values.
          4. Build the canonical manifest.
          5. Upload (manifest, root_bytes) via ``self._object_store``.
          6. INSERT an ``AuditAnchor`` row carrying the URI + version + retention.
          7. Return the persisted ``AuditAnchor``.

        Idempotent: if an anchor for ``(org, date)`` already exists,
        raises ``ValueError("already anchored")`` — A3 forbids silent
        replacement (immutability would be defeated).

        Args:
            organization_id: tenant UUID. Must match the active context.
            anchor_date:     UTC ``date`` value for the day being anchored.

        Returns:
            The persisted ``AuditAnchor`` instance (detached from session).

        Raises:
            TenantContextMissing: if no ``org_context`` is active.
            ValueError: if anchor already exists for ``(org, date)``.
        """
        # --- tenant resolution (A3 — fail loud if missing) ---
        ctx_org = current_org_id()
        if ctx_org is None:
            raise TenantContextMissing(
                "AnchorBuilder.build_anchor_for_day requires a tenant context. "
                "Wrap the work in `org_context(org_id)` or use "
                "`get_db_session(tenant_id=...)`."
            )

        # --- pre-check for prior anchor (cheap fast-fail) ---
        session = self._session_factory()
        try:
            existing = (
                session.query(AuditAnchor)
                .filter_by(
                    organization_id=organization_id,
                    anchor_date=anchor_date,
                )
                .first()
            )
            if existing is not None:
                raise ValueError(
                    f"already anchored: organization_id={organization_id} "
                    f"anchor_date={anchor_date.isoformat()}"
                )

            # --- SELECT events in the half-open UTC day interval ---
            day_start = datetime.combine(anchor_date, time(0, 0, 0), tzinfo=timezone.utc)
            day_end = day_start + timedelta(days=1)

            events = (
                session.query(AuditEventV2)
                .filter(
                    AuditEventV2.event_ts_utc >= day_start,
                    AuditEventV2.event_ts_utc < day_end,
                )
                .order_by(
                    AuditEventV2.event_ts_utc.asc(),
                    AuditEventV2.sequence_index.asc(),
                    AuditEventV2.event_id.asc(),
                )
                .all()
            )

            event_hashes: list[bytes] = [bytes(e.event_hash) for e in events]
            for i, h in enumerate(event_hashes):
                if len(h) != 32:
                    # Schema CHECK should make this unreachable; defensive.
                    raise RuntimeError(
                        f"Stored event_hash for event #{i} is not 32 bytes — "
                        f"chain corrupt."
                    )

            merkle_root = AnchorBuilder.build_merkle_root(event_hashes)

            first_event_id: Optional[str] = events[0].event_id if events else None
            last_event_id: Optional[str] = events[-1].event_id if events else None

            created_at = datetime.now(timezone.utc)

            manifest = AnchorBuilder.build_manifest(
                org_id=organization_id,
                anchor_date=anchor_date,
                merkle_root=merkle_root,
                event_hashes=event_hashes,
                first_event_id=first_event_id,
                last_event_id=last_event_id,
                created_at=created_at,
            )

            # --- upload to object store (loud failure; don't write the row) ---
            key = f"{organization_id}/{anchor_date.isoformat()}"
            uri, version_id = self._object_store.put(
                key=key, manifest=manifest, root_bytes=merkle_root,
            )

            # --- INSERT the anchor row ---
            anchor = AuditAnchor(
                anchor_id=str(uuid.uuid4()),
                organization_id=organization_id,
                anchor_date=anchor_date,
                merkle_root=merkle_root,
                event_count=len(event_hashes),
                first_event_id=first_event_id,
                last_event_id=last_event_id,
                s3_object_uri=uri,
                s3_version_id=version_id,
                # Retention horizon is backend-dependent — local-fs has none.
                # TMX-3107a will populate this from the S3 retention policy.
                s3_object_lock_until=None,
            )
            session.add(anchor)
            try:
                session.commit()
            except IntegrityError as exc:
                # Race window between the pre-check SELECT and the INSERT —
                # another caller anchored in between. Re-raise as ValueError
                # for caller-friendly handling.
                session.rollback()
                raise ValueError(
                    f"already anchored: organization_id={organization_id} "
                    f"anchor_date={anchor_date.isoformat()} (race condition)"
                ) from exc

            session.refresh(anchor)
            session.expunge(anchor)
            return anchor
        finally:
            session.close()
