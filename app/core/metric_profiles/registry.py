"""
MetricProfileRegistry — versioned content-type MQM metric profiles (TMX-MQM-2).

A *metric profile* is the content-type-specific specification the MQM engine
(TMX-MQM-3) scores against: which Error-Type Weights apply, the Passing
Threshold, the Acceptable Penalty Points per 1,000 words, the evaluation mode,
and the short-document sample floor (§5.4 of the LangOps Platform Vision).

This deliberately mirrors ``app/agents/prompts/registry.py`` (PromptRegistry):
same ``<profile_id>/v<MAJOR>.<MINOR>.<PATCH>.yaml`` layout, same class-level
cache + lock, same ``latest`` semver resolution, same ``content_hash`` so a
re-score is pinned to an exact, change-controlled profile version. Keeping the
two registries structurally identical means a future loop can extract a shared
versioned-YAML-registry helper (the "extract on the 3rd copy" rule) cleanly.

This module is the reconciliation point for the two pre-existing, disconnected
profile systems (``app/core/regulatory_profiles.py`` authority metadata and
``app/core/profile_resolver.py`` archetype/tier) — neither carried scoring
semantics. Those are wired in later (TMX-MQM-5); this registry owns the
*scoring* profile only.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Dict, List, Tuple

import yaml

PROFILES_ROOT = Path(__file__).resolve().parent

_VERSION_FILE_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)\.yaml$")

# Default Error-Type Weight when a profile does not pin a dimension explicitly.
_DEFAULT_ETW = 1.0


class MetricProfileNotFoundError(LookupError):
    """Raised when a profile id or version cannot be located on disk."""


class MetricProfileSchemaError(ValueError):
    """Raised when a profile YAML is missing a key or has the wrong type."""


@dataclass(frozen=True)
class MetricProfile:
    """A loaded content-type metric profile at a fixed version (immutable).

    ``error_type_weights`` is keyed by ``MqmDimension`` *value* strings (e.g.
    "Accuracy", "Design & markup") plus an optional "default" entry.
    """

    profile_id: str
    version: str
    display_name: str
    passing_threshold: float          # PT — calibrated 0-100 threshold (compared to CQS)
    acceptable_penalty_points: float  # APP — tolerated penalty points / 1,000 words
    evaluation: str                   # "full" | "sampled"
    sample_size_floor: int            # SQC word floor; below ⇒ insufficient-sample
    critical_auto_fail: bool
    error_type_weights: Dict[str, float] = field(default_factory=dict)
    content_hash: str = ""
    description: str = ""

    def etw(self, dimension) -> float:
        """Error-Type Weight for an ``MqmDimension`` (or its value string)."""
        key = getattr(dimension, "value", dimension)
        if key in self.error_type_weights:
            return float(self.error_type_weights[key])
        return float(self.error_type_weights.get("default", _DEFAULT_ETW))


def _compute_hash(data: dict) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _parse_version_filename(name: str) -> Tuple[int, int, int] | None:
    m = _VERSION_FILE_RE.match(name)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def _format_version(triple: Tuple[int, int, int]) -> str:
    return f"{triple[0]}.{triple[1]}.{triple[2]}"


class MetricProfileRegistry:
    """Class-level cache; one read per (profile_id, version) per process."""

    _cache: Dict[Tuple[str, str], MetricProfile] = {}
    _lock = Lock()

    @classmethod
    def load(cls, profile_id: str, version: str = "latest") -> MetricProfile:
        if version == "latest":
            version = cls._resolve_latest(profile_id)
        key = (profile_id, version)
        cached = cls._cache.get(key)
        if cached is not None:
            return cached
        with cls._lock:
            cached = cls._cache.get(key)
            if cached is not None:
                return cached
            loaded = cls._load_from_disk(profile_id, version)
            cls._cache[key] = loaded
            return loaded

    @classmethod
    def list_profiles(cls) -> List[str]:
        return sorted(
            p.name for p in PROFILES_ROOT.iterdir()
            if p.is_dir() and not p.name.startswith("__")
        )

    @classmethod
    def list_versions(cls, profile_id: str) -> List[str]:
        profile_dir = PROFILES_ROOT / profile_id
        if not profile_dir.is_dir():
            raise MetricProfileNotFoundError(f"No profile directory: {profile_id!r}")
        triples = [
            t for entry in profile_dir.iterdir()
            if (t := _parse_version_filename(entry.name)) is not None
        ]
        triples.sort()
        return [_format_version(t) for t in triples]

    @classmethod
    def _resolve_latest(cls, profile_id: str) -> str:
        versions = cls.list_versions(profile_id)
        if not versions:
            raise MetricProfileNotFoundError(
                f"No versioned profile files (v*.yaml) under {profile_id!r}"
            )
        return versions[-1]

    @classmethod
    def _load_from_disk(cls, profile_id: str, version: str) -> MetricProfile:
        path = PROFILES_ROOT / profile_id / f"v{version}.yaml"
        if not path.is_file():
            raise MetricProfileNotFoundError(
                f"Profile not found: {profile_id!r} v{version} (looked at {path})"
            )
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise MetricProfileSchemaError(f"YAML parse error in {path}: {exc}") from exc

        if not isinstance(data, dict):
            raise MetricProfileSchemaError(f"Top-level YAML must be a mapping in {path}")

        required = (
            "version", "profile_id", "display_name", "passing_threshold",
            "acceptable_penalty_points", "evaluation", "sample_size_floor",
            "critical_auto_fail",
        )
        for k in required:
            if k not in data:
                raise MetricProfileSchemaError(f"Missing required key {k!r} in {path}")
        if data["version"] != version:
            raise MetricProfileSchemaError(
                f"Version mismatch in {path}: filename v{version}, file says {data['version']}"
            )
        if data["profile_id"] != profile_id:
            raise MetricProfileSchemaError(
                f"profile_id mismatch in {path}: dir {profile_id!r}, file {data['profile_id']!r}"
            )
        if data["evaluation"] not in ("full", "sampled"):
            raise MetricProfileSchemaError(
                f"evaluation must be 'full' or 'sampled' in {path}"
            )
        if float(data["acceptable_penalty_points"]) <= 0:
            # APP is the denominator of the Scaling Factor — zero would divide-by-zero.
            raise MetricProfileSchemaError(
                f"acceptable_penalty_points must be > 0 in {path}"
            )

        etw = data.get("error_type_weights") or {}
        if not isinstance(etw, dict):
            raise MetricProfileSchemaError(f"error_type_weights must be a mapping in {path}")

        return MetricProfile(
            profile_id=profile_id,
            version=version,
            display_name=str(data["display_name"]),
            passing_threshold=float(data["passing_threshold"]),
            acceptable_penalty_points=float(data["acceptable_penalty_points"]),
            evaluation=str(data["evaluation"]),
            sample_size_floor=int(data["sample_size_floor"]),
            critical_auto_fail=bool(data["critical_auto_fail"]),
            error_type_weights={str(k): float(v) for k, v in etw.items()},
            content_hash=_compute_hash(data),
            description=str(data.get("description", "")),
        )

    @classmethod
    def _clear_cache_for_tests(cls) -> None:
        with cls._lock:
            cls._cache.clear()
