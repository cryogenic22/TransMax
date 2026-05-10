# Regulatory Pack (TMX-3500)

Per-release validation packs for pharma deployment under GAMP 5 + EU Annex 11
+ 21 CFR Part 11. Five canonical documents:

- **URS** - User Requirements Specification
- **FS**  - Functional Specification
- **IQ**  - Installation Qualification
- **OQ**  - Operational Qualification
- **PQ**  - Performance Qualification

This directory holds:

```
regulatory_pack/
  README.md                  # this file
  templates/
    URS_template.md
    FS_template.md
    IQ_template.md
    OQ_template.md
    PQ_template.md
  generators/
    __init__.py
    traceability.py          # ticket -> AC -> test -> commit harness
    pack_builder.py          # CLI orchestration
  releases/                  # gitignored except .gitkeep; per-release output
    .gitkeep
```

## Generating a pack

```bash
python -m regulatory_pack.generators.pack_builder \
    --release v3.0-rc1 \
    --output regulatory_pack/releases/v3.0-rc1/
```

The builder reads the templates, fills `$placeholder` tokens with evidence
from the running repo (worksheets in `.context/loops/`, ADRs in
`docs/decisions/`, ratchet metrics in `ratchet/baseline.json`, tests in
`tests/`, git log), and writes filled markdown into `--output`.

It also writes a standalone `traceability_matrix.json` for downstream
consumers (the future PDF renderer in TMX-3500a and the signature workflow
in TMX-3500b).

## Signing protocol

> **Important: signature blocks are intentionally empty in the templates.**
> A pack is not valid until signed. Auto-signing is forbidden by addendum
> A1 (no silent fallbacks in regulated paths) and addendum A3.

Per-document signing authority:

| Document | Signing authority |
|---|---|
| URS | Programme Lead |
| FS | Quality Lead + Reg Affairs Lead (joint) |
| IQ | Platform Lead |
| OQ | QA Lead |
| PQ | Reg Affairs Lead |

The signature block carries: role, name, ISO date, and a `signature_hash`
(detached PGP / Adobe-AATL-style detached signature - finalised in
TMX-3500b).

## Design rationale

The pack builder PULLS existing evidence; it does not duplicate it. The
authoritative sources of truth remain:

- `.context/loops/TMX-XXXX.md` for per-ticket design and ACs
- `tests/` for the OQ test plan
- `tests/evals/` for PQ eval-harness output
- `docs/decisions/` for ADRs (FS rationale)
- `ratchet/baseline.json` for the IQ code-quality posture
- `app/agents/prompts/<agent>/<version>.yaml` for prompt provenance (PQ
  reproducibility, addendum A8)

If a future change moves any of these sources, update `generators/`
modules to match.

## Deferred follow-ups

- **TMX-3500a** PDF rendering. The scaffold emits markdown; a follow-up
  ticket adds wkhtmltopdf / weasyprint / Pandoc rendering. Constraint:
  the dep choice is reviewer-visible (PDF rendering pulls fonts +
  HTML->PDF lib; budget the binary cost in the dependency review).
- **TMX-3500b** Signature workflow. Detached signature mechanism, hash
  algorithm choice, and storage location (alongside the markdown? S3
  Object Lock? Separate signing-DB?). Owner: Programme Lead governance
  decision.
- **TMX-3500c** Audit-event emission. Each `build_pack()` invocation
  should emit a `REG_PACK_GENERATED` event via the audit-v2 ledger
  (TMX-3101). Currently the v1 ledger requires `job_id` which doesn't
  fit; deferred until v2 ships.
- **TMX-3500d** CI integration. A GHA workflow that emits a per-release
  pack as a build artefact when a `vN.M.X` tag is pushed. Trivial once
  the CLI is stable.
- **TMX-3500e** Test-results auto-population. Wire `pytest --json-report`
  output into the OQ document so the test-results table is filled
  automatically. Same for `tests/evals/` -> PQ.
