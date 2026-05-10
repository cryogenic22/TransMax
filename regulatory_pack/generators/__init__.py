"""Generators for the Regulatory Pack scaffold (TMX-3500).

- `traceability` - walks `.context/loops/`, `tests/`, and git, producing
  a per-ticket -> per-AC -> per-test -> per-commit matrix.
- `pack_builder` - reads templates, fills placeholders with evidence
  pulled by the traceability harness plus repo metadata, writes filled
  markdown to a per-release output directory.
"""
