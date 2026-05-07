"""
PromptRegistry — loads versioned prompt YAML files and returns frozen records.

See `app/agents/prompts/__init__.py` for the public-API contract and the
addenda (A6, A8) that motivate this module. TMX-3200 + TMX-3201.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Dict, List, Tuple

import yaml


PROMPTS_ROOT = Path(__file__).resolve().parent

# Filenames are `v<MAJOR>.<MINOR>.<PATCH>.yaml`. Strict format so semver-aware
# sorting works on lex order.
_VERSION_FILE_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)\.yaml$")


class PromptNotFoundError(LookupError):
    """Raised when an agent or version cannot be located on disk."""


class PromptSchemaError(ValueError):
    """Raised when a YAML file is missing a required key or has the wrong type."""


@dataclass(frozen=True)
class PromptVersion:
    """A loaded prompt at a fixed version. Immutable on purpose: the registry
    caches these and re-issues the same instance to repeat callers."""

    agent: str
    version: str
    system: str
    user: str
    content_hash: str  # sha256(system + "\n---\n" + user), hex
    description: str = ""


def _compute_hash(system: str, user: str) -> str:
    # The "\n---\n" separator means moving content between system and user
    # changes the hash, even if the concatenation would otherwise coincide.
    payload = (system + "\n---\n" + user).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _parse_version_filename(name: str) -> Tuple[int, int, int] | None:
    m = _VERSION_FILE_RE.match(name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _format_version(triple: Tuple[int, int, int]) -> str:
    return f"{triple[0]}.{triple[1]}.{triple[2]}"


class PromptRegistry:
    """Class-level cache; one read per (agent, version) per process."""

    _cache: Dict[Tuple[str, str], PromptVersion] = {}
    _lock = Lock()

    @classmethod
    def load(cls, agent: str, version: str = "latest") -> PromptVersion:
        """Return the prompt for `agent` at `version`. `latest` resolves to
        the highest semver under `<agent>/`."""
        if version == "latest":
            version = cls._resolve_latest(agent)

        key = (agent, version)
        # Fast path: cached.
        cached = cls._cache.get(key)
        if cached is not None:
            return cached

        with cls._lock:
            # Re-check after lock — another thread may have populated.
            cached = cls._cache.get(key)
            if cached is not None:
                return cached
            loaded = cls._load_from_disk(agent, version)
            cls._cache[key] = loaded
            return loaded

    @classmethod
    def list_versions(cls, agent: str) -> List[str]:
        """Return all versions present on disk for `agent`, ascending."""
        agent_dir = PROMPTS_ROOT / agent
        if not agent_dir.is_dir():
            raise PromptNotFoundError(f"No prompt directory for agent: {agent!r}")
        triples: List[Tuple[int, int, int]] = []
        for entry in agent_dir.iterdir():
            triple = _parse_version_filename(entry.name)
            if triple is not None:
                triples.append(triple)
        triples.sort()
        return [_format_version(t) for t in triples]

    @classmethod
    def _resolve_latest(cls, agent: str) -> str:
        versions = cls.list_versions(agent)
        if not versions:
            raise PromptNotFoundError(
                f"No versioned prompt files (v*.yaml) found under agent: {agent!r}"
            )
        return versions[-1]

    @classmethod
    def _load_from_disk(cls, agent: str, version: str) -> PromptVersion:
        path = PROMPTS_ROOT / agent / f"v{version}.yaml"
        if not path.is_file():
            raise PromptNotFoundError(
                f"Prompt not found: agent={agent!r} version={version!r} (looked at {path})"
            )
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise PromptSchemaError(f"YAML parse error in {path}: {exc}") from exc

        if not isinstance(data, dict):
            raise PromptSchemaError(f"Top-level YAML must be a mapping in {path}")

        for key in ("version", "system", "user"):
            if key not in data:
                raise PromptSchemaError(f"Missing required key {key!r} in {path}")
            if not isinstance(data[key], str):
                raise PromptSchemaError(f"Key {key!r} in {path} must be a string")

        if data["version"] != version:
            raise PromptSchemaError(
                f"Version mismatch in {path}: filename says {version}, "
                f"file contents say {data['version']}"
            )

        system = data["system"]
        user = data["user"]
        return PromptVersion(
            agent=agent,
            version=version,
            system=system,
            user=user,
            content_hash=_compute_hash(system, user),
            description=str(data.get("description", "")),
        )

    @classmethod
    def _clear_cache_for_tests(cls) -> None:
        """Test-only hook to reset the cache between tests that mutate disk."""
        with cls._lock:
            cls._cache.clear()
