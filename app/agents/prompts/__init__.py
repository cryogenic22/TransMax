"""
Prompt registry for TransMax LLM-driven agents.

Per addendum A8 (pin every prompt to a version): prompts live in
`app/agents/prompts/<agent>/v<X.Y.Z>.yaml`, NOT as inline Python string
constants. Each YAML carries `version`, `system`, `user`, and
`description`. The registry returns frozen `PromptVersion` records
including a stable SHA-256 content hash that an audit event can record
in the JobConfigSnapshot (per addendum A6).

Public API:
    from app.agents.prompts import PromptRegistry, PromptVersion
    p = PromptRegistry.load("translator")              # latest
    p = PromptRegistry.load("translator", "1.0.0")     # specific
    versions = PromptRegistry.list_versions("translator")
"""
from app.agents.prompts.registry import (
    PromptNotFoundError,
    PromptRegistry,
    PromptSchemaError,
    PromptVersion,
)

__all__ = [
    "PromptRegistry",
    "PromptVersion",
    "PromptNotFoundError",
    "PromptSchemaError",
]
