"""Regulatory Pack scaffold (TMX-3500).

For pharma deployment under GAMP 5 + EU Annex 11 + 21 CFR Part 11, every
release ships a "validation pack" - five canonical documents proving the
system meets its requirements:

  - URS - User Requirements Specification
  - FS  - Functional Specification
  - IQ  - Installation Qualification
  - OQ  - Operational Qualification
  - PQ  - Performance Qualification

This package provides the SCAFFOLD - templates plus a generator that pulls
existing repo artefacts (worksheets, ADRs, tests, ratchet baseline) into
filled markdown documents. Per-release packs are written to
`regulatory_pack/releases/<release>/` (gitignored except `.gitkeep`).

PDF rendering and signature workflow are out of scope for the scaffold;
see TMX-3500a / TMX-3500b.
"""
