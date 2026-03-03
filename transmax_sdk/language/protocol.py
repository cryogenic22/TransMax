"""Language subsystem protocols."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from transmax_sdk.types import LanguageDetectionResult, RouteStrategy


@runtime_checkable
class LanguagePackProtocol(Protocol):
    """Interface for language-specific validation packs."""

    @property
    def code(self) -> str: ...

    @property
    def script_direction(self) -> str: ...

    def check_negation(self, source_text: str, target_text: str) -> List[Dict[str, Any]]: ...

    def check_numbers(self, source_text: str, target_text: str) -> List[Dict[str, Any]]: ...

    def check_punctuation(self, target_text: str) -> List[Dict[str, Any]]: ...


@runtime_checkable
class LanguagePackRegistryProtocol(Protocol):
    """Interface for language pack registries."""

    def get_pack(self, lang_code: str) -> Any: ...

    def register_pack(self, lang_code: str, pack: Any) -> None: ...
