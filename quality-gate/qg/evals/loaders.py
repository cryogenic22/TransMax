from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model import EvalCase, EvalSuite


class DatasetLoadError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Dataset:
    suite: EvalSuite
    cases: list[EvalCase]
    source_path: Path


def discover_datasets(root: Path, datasets_path: str) -> list[Path]:
    base = (root / datasets_path).resolve()
    if not base.exists():
        return []
    out: list[Path] = []
    for ext in ("*.json", "*.jsonl", "*.csv", "*.yaml", "*.yml"):
        out.extend(sorted(base.rglob(ext)))
    return out


def load_dataset(path: Path) -> Dataset:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _load_json(path)
    if suffix == ".jsonl":
        return _load_jsonl(path)
    if suffix == ".csv":
        return _load_csv(path)
    if suffix in {".yaml", ".yml"}:
        return _load_yaml_optional(path)
    raise DatasetLoadError(f"Unsupported dataset type: {path.name}")


def _load_json(path: Path) -> Dataset:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return _dataset_from_mapping(path, raw)


def _load_jsonl(path: Path) -> Dataset:
    suite = EvalSuite(name=path.stem)
    cases: list[EvalCase] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise DatasetLoadError(f"Invalid JSON on line {i} in {path.name}") from exc
        cases.append(_case_from_mapping(obj, default_id=f"line_{i}"))
    return Dataset(suite=suite, cases=cases, source_path=path)


def _load_csv(path: Path) -> Dataset:
    suite = EvalSuite(name=path.stem)
    cases: list[EvalCase] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row_idx, row in enumerate(reader, 1):
            case_id = (row.get("id") or f"row_{row_idx}").strip()
            try:
                input_obj = json.loads(row.get("input", "{}") or "{}")
                expected_obj = json.loads(row.get("expected", "{}") or "{}")
            except json.JSONDecodeError as exc:
                raise DatasetLoadError(
                    f"CSV {path.name} row {row_idx} has invalid JSON in input/expected"
                ) from exc
            cases.append(EvalCase(id=case_id, input=dict(input_obj), expected=dict(expected_obj)))
    return Dataset(suite=suite, cases=cases, source_path=path)


def _load_yaml_optional(path: Path) -> Dataset:
    try:
        import yaml  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover
        raise DatasetLoadError(
            f"YAML dataset requires PyYAML. Install 'pyyaml' or use JSON/CSV instead: {path.name}"
        ) from exc
    safe_load = getattr(yaml, "safe_load", None)
    if safe_load is None:
        raise DatasetLoadError(f"PyYAML does not expose safe_load; cannot read {path.name}")
    raw = safe_load(path.read_text(encoding="utf-8"))
    return _dataset_from_mapping(path, raw)


def _dataset_from_mapping(path: Path, raw: Any) -> Dataset:
    if not isinstance(raw, dict):
        raise DatasetLoadError(f"Dataset must be an object at top-level: {path.name}")

    meta = raw.get("metadata") or {}
    suite_name = str((meta.get("name") or raw.get("suite") or path.stem) or path.stem)
    suite = EvalSuite(name=suite_name, metadata=dict(meta) if isinstance(meta, dict) else {})

    cases_raw = raw.get("cases")
    if not isinstance(cases_raw, list):
        raise DatasetLoadError(f"Dataset missing 'cases' list: {path.name}")
    cases = [
        _case_from_mapping(item, default_id=f"case_{i + 1}") for i, item in enumerate(cases_raw)
    ]
    return Dataset(suite=suite, cases=cases, source_path=path)


def _case_from_mapping(raw: Any, *, default_id: str) -> EvalCase:
    mapping = _ensure_mapping(raw, "Case must be an object.")
    case_id = str(mapping.get("id") or default_id)
    input_obj = _ensure_mapping(
        mapping.get("input") or {}, f"Case '{case_id}' input must be an object."
    )
    expected_obj = mapping.get("expected")
    expected = None
    if expected_obj is not None:
        expected = _ensure_mapping(
            expected_obj,
            f"Case '{case_id}' expected must be an object when provided.",
        )

    assertions_raw = _ensure_list(
        mapping.get("assertions") or [], f"Case '{case_id}' assertions must be a list."
    )
    tags_raw = _ensure_list(mapping.get("tags") or [], f"Case '{case_id}' tags must be a list.")
    metadata = _ensure_mapping(
        mapping.get("metadata") or {}, f"Case '{case_id}' metadata must be an object."
    )

    assertions = [dict(a) for a in assertions_raw if isinstance(a, dict)]
    tags = tuple(str(t) for t in tags_raw)
    return EvalCase(
        id=case_id,
        input=dict(input_obj),
        expected=expected,
        assertions=assertions,
        tags=tags,
        metadata=dict(metadata),
    )


def _ensure_mapping(value: Any, message: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    raise DatasetLoadError(message)


def _ensure_list(value: Any, message: str) -> list[Any]:
    if isinstance(value, list):
        return value
    raise DatasetLoadError(message)
