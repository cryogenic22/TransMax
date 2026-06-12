"""
TMX-PARSE-1 — pluggable document-parser backends behind a canonical IR.

Public surface:

    from app.services.parsing import get_parser, ParsedDocument, ElementType
    doc = get_parser().parse(path)          # backend chosen by settings.parser_backend
    blocks = doc.to_legacy_blocks()         # backward-compatible {"text","type","meta"}

See ADR-0005 and `.context/loops/TMX-PARSE-1.md`.
"""
from app.services.parsing.base import (
    DocumentParser,
    ElementType,
    ParsedBlock,
    ParsedDocument,
    ParserError,
    ParserUnavailable,
)
from app.services.parsing.registry import available_backends, get_parser, register_backend

__all__ = [
    "DocumentParser",
    "ElementType",
    "ParsedBlock",
    "ParsedDocument",
    "ParserError",
    "ParserUnavailable",
    "get_parser",
    "register_backend",
    "available_backends",
]
