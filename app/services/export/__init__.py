"""
TMX-EXPORT-1 — pluggable document-export backends (ADR-0006).

Symmetric with ``app/services/parsing``: a registry keyed on
``settings.export_backend`` selects a backend; callers never branch on format.
The per-source *intelligence* (what to translate, which font, how to fit) lives
in format-agnostic services (``classify``/``fonts``/``layout``) that operate on a
generic ``LayoutBlock`` — so the same logic generalises across documents instead
of being hard-coded to a source type.
"""
from app.services.export.base import (  # noqa: F401
    DocumentExporter,
    ExporterUnavailable,
    ExportError,
    ExportResult,
    FidelityReport,
)
from app.services.export.registry import available_backends, get_exporter  # noqa: F401
