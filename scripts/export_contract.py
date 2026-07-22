#!/usr/bin/env python3
"""TMX-SEAM-CONTRACT / ADR-0009 clause 3 — export the FastAPI OpenAPI schema.

Dumps `app.main.app.openapi()` to `contract/openapi.json` so reSCApe can
generate a typed client against TransMax's v1 contract (CROSS-REPO-PROTOCOL
Rule 3: "reSCApe consumes generated types into `packages/contracts`").

Importing `app.main` builds the FastAPI app object (routes, schemas) but does
NOT start it — `init_db()` and table creation only run inside the ASGI
`lifespan` context manager, which this script never enters. No database
connection is required to export the schema.

Usage:
    python scripts/export_contract.py
    python scripts/export_contract.py --output contract/openapi.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "contract" / "openapi.json"


def _merge_unwired_contract_schemas(schema: dict[str, object]) -> None:
    """Merge in the ADR-0009 clause 3 result-block models that no live route
    references yet.

    FastAPI's `app.openapi()` only walks schemas reachable from a registered
    route's request/response models. `SegmentResult`, `JobResultResponse`
    and their nested types (`TranslationDisposition`, `MqmSummary`,
    `ProvenanceRecord`, `AuditRef`) are deliberately NOT wired to a route
    this loop (see worksheet scope note) — but reSCApe still needs their
    shape to generate a typed client ahead of the wiring loop, per
    CROSS-REPO-PROTOCOL Rule 3. `pydantic.json_schema.models_json_schema`
    walks each model's field graph directly (independent of route
    registration) and, pointed at the same `#/components/schemas/{model}`
    ref template FastAPI itself uses, produces defs that merge in place.
    """
    from pydantic.json_schema import models_json_schema
    from app.schemas.api_v1 import (
        AuditRef,
        ConstraintPack,
        JobResultResponse,
        MqmSummary,
        ProvenanceRecord,
        SegmentResult,
        SourceReference,
        TermbaseRef,
    )

    _, top_level = models_json_schema(
        [
            (SourceReference, "serialization"),
            (ConstraintPack, "serialization"),
            (TermbaseRef, "serialization"),
            (MqmSummary, "serialization"),
            (ProvenanceRecord, "serialization"),
            (AuditRef, "serialization"),
            (SegmentResult, "serialization"),
            (JobResultResponse, "serialization"),
        ],
        ref_template="#/components/schemas/{model}",
    )
    components = schema.setdefault("components", {})
    assert isinstance(components, dict)
    schemas = components.setdefault("schemas", {})
    assert isinstance(schemas, dict)
    defs = top_level.get("$defs", {})
    assert isinstance(defs, dict)
    schemas.update(defs)


def export_openapi(output_path: Path) -> dict[str, object]:
    """Build the FastAPI app, extract its OpenAPI schema, write it to disk.

    Returns the schema dict (so callers/tests can assert on it without a
    second disk read).
    """
    sys.path.insert(0, str(REPO_ROOT))
    from app.main import app  # noqa: E402 — import after sys.path setup
    from app.schemas.api_v1 import CONTRACT_VERSION  # noqa: E402

    schema = app.openapi()
    info = schema.get("info")
    assert isinstance(info, dict)
    info["x-contract-version"] = CONTRACT_VERSION
    _merge_unwired_contract_schemas(schema)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return schema


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output path for the OpenAPI JSON (default: {DEFAULT_OUTPUT.relative_to(REPO_ROOT)})",
    )
    args = parser.parse_args()

    schema = export_openapi(args.output)

    raw_info = schema.get("info", {})
    info: dict[str, object] = raw_info if isinstance(raw_info, dict) else {}
    contract_version = info.get("x-contract-version", "unknown")

    raw_components = schema.get("components", {})
    components: dict[str, object] = raw_components if isinstance(raw_components, dict) else {}
    raw_schemas = components.get("schemas", {})
    schema_count = len(raw_schemas) if isinstance(raw_schemas, dict) else 0

    print(f"Wrote {args.output} ({schema_count} schemas, contract_version join key: {contract_version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
