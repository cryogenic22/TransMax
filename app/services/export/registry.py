"""
TMX-EXPORT-1 — export-backend registry + factory (ADR-0006 AC-1).

Config not branching: the backend is chosen by name from a registry keyed on
``settings.export_backend``, mirroring ``app/services/parsing/registry.py``.
"""
from __future__ import annotations

from typing import Callable, Optional

from app.services.export.base import DocumentExporter, ExportError

_BACKENDS: dict[str, Callable[[], DocumentExporter]] = {}


def register_backend(name: str, factory: Callable[[], DocumentExporter]) -> None:
    _BACKENDS[name.lower()] = factory


def available_backends() -> list[str]:
    return sorted(_BACKENDS)


def get_exporter(name: Optional[str] = None) -> DocumentExporter:
    """Return the export backend selected by ``name`` or ``settings.export_backend``.

    A3: an unknown name raises ``ExportError`` (never a silent fallback). A
    backend that is registered but cannot run here raises ``ExporterUnavailable``
    from its own ``export()``.
    """
    if name is None:
        from app.core.config import settings

        name = getattr(settings, "export_backend", "docx")
    key = (name or "docx").lower()
    factory = _BACKENDS.get(key)
    if factory is None:
        raise ExportError(
            f"Unknown export backend '{name}'. "
            f"Registered: {', '.join(available_backends()) or '(none)'}."
        )
    return factory()


def _register_builtin_backends() -> None:
    from app.services.export.docx_backend import DocxExporter
    from app.services.export.pdf_overlay_backend import PdfOverlayExporter
    from app.services.export.pdf_render_backend import PdfRenderExporter

    register_backend("docx", DocxExporter)
    register_backend("pdf_overlay", PdfOverlayExporter)
    register_backend("pdf_render", PdfRenderExporter)


_register_builtin_backends()
