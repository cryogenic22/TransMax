"""TMX-EXPORT-1 — registry fail-loud + selection."""
import pytest

from app.services.export.base import ExportError
from app.services.export.registry import available_backends, get_exporter


def test_builtins_registered():
    assert "docx" in available_backends()
    assert "pdf_overlay" in available_backends()


def test_select_by_name():
    assert get_exporter("docx").name == "docx"
    assert get_exporter("pdf_overlay").name == "pdf_overlay"


def test_unknown_backend_fails_loud():
    with pytest.raises(ExportError):
        get_exporter("does_not_exist")


def test_default_from_settings(monkeypatch):
    from app.core import config
    monkeypatch.setattr(config.settings, "export_backend", "pdf_overlay", raising=False)
    assert get_exporter().name == "pdf_overlay"
