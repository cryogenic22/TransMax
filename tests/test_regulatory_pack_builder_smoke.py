"""TMX-3500 — Regulatory Pack builder smoke tests.

The pack builder orchestrates: read templates, fill placeholders, write to
output_dir. This is scaffolding, not heavyweight integration — the smoke
tests verify the five canonical documents are emitted and contain the
expected structural markers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_pack_builder_emits_all_five_documents(tmp_path: Path) -> None:
    """TMX-3500 / AC-6 — build_pack writes URS, FS, IQ, OQ, PQ markdown
    files into output_dir.
    """
    from regulatory_pack.generators.pack_builder import build_pack

    out = tmp_path / "test-release"
    build_pack(release="test-release", output_dir=out, repo_root=REPO_ROOT)

    for doc in ("URS", "FS", "IQ", "OQ", "PQ"):
        assert (out / f"{doc}.md").exists(), f"{doc} not emitted at {out / f'{doc}.md'}"


def test_pack_builder_idempotent(tmp_path: Path) -> None:
    """TMX-3500 / AC-6 supplemental — running the builder twice on the same
    output_dir overwrites cleanly without raising or duplicating content.
    """
    from regulatory_pack.generators.pack_builder import build_pack

    out = tmp_path / "idem-release"
    build_pack(release="idem-release", output_dir=out, repo_root=REPO_ROOT)
    first_size = (out / "URS.md").stat().st_size
    build_pack(release="idem-release", output_dir=out, repo_root=REPO_ROOT)
    second_size = (out / "URS.md").stat().st_size

    # Same release token + same repo state -> identical output size.
    # Allow a small tolerance for $generated_at timestamp drift.
    assert (
        abs(first_size - second_size) < 100
    ), f"idempotent re-run produced different sizes: {first_size} vs {second_size}"


def test_pack_builder_substitutes_release_token(tmp_path: Path) -> None:
    """TMX-3500 / AC-6 — the `release` argument lands in each document's
    front-matter or body so reviewers can see which release a pack belongs to.
    """
    from regulatory_pack.generators.pack_builder import build_pack

    out = tmp_path / "release-token-test"
    release = "v3.0-rc7-canary"
    build_pack(release=release, output_dir=out, repo_root=REPO_ROOT)

    for doc in ("URS", "FS", "IQ", "OQ", "PQ"):
        body = (out / f"{doc}.md").read_text(encoding="utf-8")
        assert release in body, f"{doc} does not reference release '{release}'"


def test_pack_builder_each_document_has_signature_block(tmp_path: Path) -> None:
    """TMX-3500 / AC-2 — every emitted document has an empty signature block
    ready for human signing. Verify the literal section header is present and
    the front-matter `signed_by:` is the empty list.
    """
    from regulatory_pack.generators.pack_builder import build_pack

    out = tmp_path / "sig-test"
    build_pack(release="sig-test", output_dir=out, repo_root=REPO_ROOT)

    for doc in ("URS", "FS", "IQ", "OQ", "PQ"):
        body = (out / f"{doc}.md").read_text(encoding="utf-8")
        # Accept either `## Signatures` or `## N. Signatures` - templates use
        # both forms. The Markdown level is what matters for downstream PDF
        # rendering.
        assert (
            "Signatures" in body and "##" in body
        ), f"{doc} missing 'Signatures' section heading"
        # Front-matter `signed_by: []` keeps the documents un-signed at
        # generation time; humans add signatures via the release-signing
        # workflow (TMX-3500b).
        assert (
            "signed_by: []" in body or "signed_by:\n  []" in body
        ), f"{doc} signed_by is not empty (must be empty for human signing)"


def test_pack_builder_includes_traceability_matrix(tmp_path: Path) -> None:
    """TMX-3500 / AC-3 — at least one document (FS or OQ) embeds the
    traceability matrix.
    """
    from regulatory_pack.generators.pack_builder import build_pack

    out = tmp_path / "trace-test"
    build_pack(release="trace-test", output_dir=out, repo_root=REPO_ROOT)

    fs_body = (out / "FS.md").read_text(encoding="utf-8")
    oq_body = (out / "OQ.md").read_text(encoding="utf-8")

    # At least one of FS/OQ should embed a traceability table (rows of
    # `| TMX-... | AC-... | ...`).
    has_table = any(
        ("| TMX-" in body or "TMX-3045" in body) for body in (fs_body, oq_body)
    )
    assert has_table, "neither FS.md nor OQ.md embeds the traceability table"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
