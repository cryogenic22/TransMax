"""
TMX-3104 — Shared canonical constants for the v2 audit chain spec.

These constants are the SPEC. They are intentionally shared between the
writer (``app/services/audit_writer_v2.py``) and the verifier
(``app/services/audit_verifier_v2.py``) so that there is exactly ONE
declaration of the spec across the codebase.

The CANONICAL ALGORITHM functions (``compute_payload_hash`` /
``recompute_payload_hash`` etc.) are deliberately NOT shared. Two
independent implementations of the same spec, byte-for-byte agreement, IS
the verification. See TMX-3104 worksheet stage 3 for rationale.

If these constants change, the chain spec has changed — open a one-way
migration loop and bump ``DOMAIN_TAG`` to a new version (e.g.
``transmax.audit.v2\\0``). All existing chains MUST keep verifying under
the OLD constant; chains written under the new constant are a separate
domain by construction.
"""
from __future__ import annotations

# The 18-byte canonical domain tag (17 ASCII bytes + 1 NUL terminator).
# NUL-terminator is part of the tag — it domain-separates this chain from
# any future tag without a trailing NUL. SHA-256 domain separation: even
# if every other input byte collides, the tag bytes guarantee distinct
# hash outputs.
#
# Historical note: an earlier TMX-3101 writer docstring claimed "20 bytes".
# That was a narrative-only error (the byte literal was always 18 bytes and
# the pinned hex digest in tests/test_audit_writer_v2.py is computed from
# the 18-byte literal). The docstrings were corrected by
# TMX-CORRECTIVE-20260511; the assertion below is the load-bearing check
# that prevents any future re-jigger of the constant from drifting silently.
# The 18-byte tag IS the spec.
DOMAIN_TAG: bytes = b"transmax.audit.v1\0"

# The 32-byte zero sentinel used as ``previous_hash`` for
# ``sequence_index == 0``. The all-zero pattern is detectable AND
# domain-separates from any real SHA-256 output (collision probability
# 2^-256, cryptographically impossible).
#
# Closes review finding C-04: the v1 writer used the literal string
# ``"GENESIS_HASH"`` which made the genesis hash a 13-byte ASCII string
# while every other chain entry was a 64-char hex digest — a textbook
# domain-separation bug.
GENESIS_HASH: bytes = b"\x00" * 32

# Sentinel checks
assert len(DOMAIN_TAG) == 18, f"DOMAIN_TAG must be 18 bytes, got {len(DOMAIN_TAG)}"
assert len(GENESIS_HASH) == 32, f"GENESIS_HASH must be 32 bytes, got {len(GENESIS_HASH)}"
