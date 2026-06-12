"""
TMX-PARSE-1 — parser-backend registry + factory.

Config not branching: the backend is chosen by name from a registry keyed on
``settings.parser_backend``, not by an ``if file_ext`` ladder in the caller.
Open for extension — a new backend registers itself; callers don't change.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

from app.services.parsing.base import DocumentParser, ParserError

logger = logging.getLogger(__name__)

# name -> zero-arg factory returning a DocumentParser. Factories are lazy so
# importing the registry never imports a heavy backend (e.g. Docling/torch).
_BACKENDS: dict[str, Callable[[], DocumentParser]] = {}


def register_backend(name: str, factory: Callable[[], DocumentParser]) -> None:
    """Register a backend factory under ``name`` (lower-cased)."""
    _BACKENDS[name.lower()] = factory


def available_backends() -> list[str]:
    """Names of all registered backends (does NOT check runtime availability)."""
    return sorted(_BACKENDS)


def get_parser(name: Optional[str] = None) -> DocumentParser:
    """Return the parser backend selected by ``name`` or ``settings.parser_backend``.

    A3: an unknown backend name raises ``ParserError`` — it never silently
    falls back to a worse parser. (A backend that is *registered* but cannot
    run in this environment raises ``ParserUnavailable`` from its own
    ``parse()`` — that distinction is the caller's to handle.)
    """
    if name is None:
        from app.core.config import settings

        name = getattr(settings, "parser_backend", "pypdf")
    key = (name or "pypdf").lower()
    factory = _BACKENDS.get(key)
    if factory is None:
        raise ParserError(
            f"Unknown parser backend '{name}'. "
            f"Registered: {', '.join(available_backends()) or '(none)'}."
        )
    return factory()


def _register_builtin_backends() -> None:
    """Register the built-in backends by name (factories stay lazy)."""
    from app.services.parsing.azure_backend import AzureDocIntelligenceParser
    from app.services.parsing.docling_backend import DoclingParser
    from app.services.parsing.google_backend import GoogleDocumentAIParser
    from app.services.parsing.pypdf_backend import PyPdfParser

    register_backend("pypdf", PyPdfParser)
    register_backend("docling", DoclingParser)
    register_backend("azure", AzureDocIntelligenceParser)
    register_backend("google", GoogleDocumentAIParser)


_register_builtin_backends()
