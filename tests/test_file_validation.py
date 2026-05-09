"""
TMX-3705 — File-upload validation contract tests.

Covers:
  - valid PDF / DOCX / TXT magic bytes pass
  - .pdf with EXE magic rejects with magic_byte_mismatch
  - .pdf with no magic rejects
  - oversized file rejects + partial cleaned up
  - TXT with NUL bytes rejects
  - empty file rejects
  - unsupported extension rejects with unsupported_extension
  - AV scan hook fires once on success
"""
from __future__ import annotations

import asyncio
import io
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.services import file_validation
from app.services.file_validation import (
    FileValidationError,
    validate_and_save_upload,
)


# ── helpers ─────────────────────────────────────────────────────────────


def _make_upload(filename: str, body: bytes) -> UploadFile:
    """Build an UploadFile pretending to be a multipart upload."""
    return UploadFile(
        file=io.BytesIO(body),
        filename=filename,
        headers=Headers({"content-type": "application/octet-stream"}),
    )


PDF_BYTES = b"%PDF-1.4\n%test pdf body\n"
DOCX_BYTES = b"PK\x03\x04" + b"\x00" * 200 + b"docx-zip-body"
TXT_BYTES = b"Hello world.\nMultiple lines of plain ASCII text."
EXE_BYTES = b"MZ\x90\x00" + b"\x00" * 200  # Windows executable header


# ── happy paths ─────────────────────────────────────────────────────────


def test_valid_pdf_accepts(tmp_path: Path) -> None:
    dest = tmp_path / "out.pdf"
    upload = _make_upload("source.pdf", PDF_BYTES)
    size = asyncio.run(
        validate_and_save_upload(upload, str(dest), allowed_extensions=(".pdf",))
    )
    assert size == len(PDF_BYTES)
    assert dest.read_bytes() == PDF_BYTES


def test_valid_docx_accepts(tmp_path: Path) -> None:
    dest = tmp_path / "out.docx"
    upload = _make_upload("source.docx", DOCX_BYTES)
    size = asyncio.run(
        validate_and_save_upload(upload, str(dest), allowed_extensions=(".docx",))
    )
    assert size == len(DOCX_BYTES)
    assert dest.read_bytes() == DOCX_BYTES


def test_valid_txt_accepts(tmp_path: Path) -> None:
    dest = tmp_path / "out.txt"
    upload = _make_upload("source.txt", TXT_BYTES)
    size = asyncio.run(
        validate_and_save_upload(upload, str(dest), allowed_extensions=(".txt",))
    )
    assert size == len(TXT_BYTES)


# ── magic-byte rejections ───────────────────────────────────────────────


def test_pdf_with_exe_magic_rejects(tmp_path: Path) -> None:
    dest = tmp_path / "evil.pdf"
    upload = _make_upload("evil.pdf", EXE_BYTES)
    with pytest.raises(FileValidationError) as exc_info:
        asyncio.run(
            validate_and_save_upload(upload, str(dest), allowed_extensions=(".pdf",))
        )
    assert exc_info.value.detail["category"] == "magic_byte_mismatch"
    # Partial file cleaned up
    assert not dest.exists()


def test_pdf_with_no_magic_rejects(tmp_path: Path) -> None:
    dest = tmp_path / "blank.pdf"
    upload = _make_upload("blank.pdf", b"")
    with pytest.raises(FileValidationError) as exc_info:
        asyncio.run(
            validate_and_save_upload(upload, str(dest), allowed_extensions=(".pdf",))
        )
    assert exc_info.value.detail["category"] == "magic_byte_mismatch"


def test_txt_with_nul_bytes_rejects(tmp_path: Path) -> None:
    dest = tmp_path / "binary.txt"
    upload = _make_upload("binary.txt", b"text\x00binary\x00")
    with pytest.raises(FileValidationError) as exc_info:
        asyncio.run(
            validate_and_save_upload(upload, str(dest), allowed_extensions=(".txt",))
        )
    assert exc_info.value.detail["category"] == "magic_byte_mismatch"


def test_empty_txt_rejects(tmp_path: Path) -> None:
    dest = tmp_path / "empty.txt"
    upload = _make_upload("empty.txt", b"")
    with pytest.raises(FileValidationError) as exc_info:
        asyncio.run(
            validate_and_save_upload(upload, str(dest), allowed_extensions=(".txt",))
        )
    assert exc_info.value.detail["category"] == "empty_file"


# ── extension rejection ─────────────────────────────────────────────────


def test_exe_extension_rejects(tmp_path: Path) -> None:
    dest = tmp_path / "out.exe"
    upload = _make_upload("nasty.exe", EXE_BYTES)
    with pytest.raises(FileValidationError) as exc_info:
        asyncio.run(
            validate_and_save_upload(upload, str(dest), allowed_extensions=(".pdf", ".docx", ".txt"))
        )
    assert exc_info.value.detail["category"] == "unsupported_extension"


# ── size cap ────────────────────────────────────────────────────────────


def test_oversized_pdf_rejects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Tighten the cap for the test so we don't actually allocate 50MB.
    monkeypatch.setattr(file_validation, "MAX_UPLOAD_BYTES", 8192)  # 8KB
    dest = tmp_path / "huge.pdf"
    big_body = PDF_BYTES + b"\x00" * (16384 - len(PDF_BYTES))  # 16KB
    upload = _make_upload("huge.pdf", big_body)
    with pytest.raises(FileValidationError) as exc_info:
        asyncio.run(
            validate_and_save_upload(upload, str(dest), allowed_extensions=(".pdf",))
        )
    assert exc_info.value.detail["category"] == "file_too_large"
    # Partial file cleaned up
    assert not dest.exists()


# ── AV trigger ──────────────────────────────────────────────────────────


def test_av_scan_request_fires_once_on_success(tmp_path: Path) -> None:
    dest = tmp_path / "out.pdf"
    upload = _make_upload("source.pdf", PDF_BYTES)
    with patch.object(file_validation, "emit_av_scan_request") as av_mock:
        asyncio.run(
            validate_and_save_upload(
                upload,
                str(dest),
                allowed_extensions=(".pdf",),
                av_metadata={"doc_id": "doc-123", "uploaded_by": "user-456"},
            )
        )
    av_mock.assert_called_once()
    args, kwargs = av_mock.call_args
    assert args[0] == str(dest)
    assert args[1]["doc_id"] == "doc-123"
    assert args[1]["uploaded_by"] == "user-456"
    assert args[1]["filename"] == "source.pdf"


def test_av_scan_request_does_not_fire_on_rejection(tmp_path: Path) -> None:
    dest = tmp_path / "evil.pdf"
    upload = _make_upload("evil.pdf", EXE_BYTES)
    with patch.object(file_validation, "emit_av_scan_request") as av_mock:
        with pytest.raises(FileValidationError):
            asyncio.run(
                validate_and_save_upload(upload, str(dest), allowed_extensions=(".pdf",))
            )
    av_mock.assert_not_called()
