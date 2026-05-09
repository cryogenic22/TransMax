"""
File-upload validation service.

Per addendum A3 (no silent fallbacks in regulated paths) + plan E5: every
upload route validates the file's magic bytes, caps the size, and emits
an AV scan trigger. Rejection raises HTTPException 400 with a structured
detail describing the failure category.

Usage:
    from app.services.file_validation import validate_and_save_upload

    async def my_upload_route(file: UploadFile = File(...)):
        size = await validate_and_save_upload(
            upload_file=file,
            dest_path="/uploads/abc.pdf",
            allowed_extensions=(".pdf", ".docx", ".txt"),
        )
        # size is the validated byte count; file is on disk; AV hook fired.

See TMX-3705 worksheet for spec; sister tickets:
  - TMX-3706: deeper DOCX vs XLSX vs PPTX disambiguation (peek inside ZIP)
  - TMX-3707: AV scanner integration (clamd / Cloud DLP)
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterable, Optional

import aiofiles
from fastapi import HTTPException, UploadFile

logger = logging.getLogger(__name__)


# Default 50 MB. Override via env at deploy time.
MAX_UPLOAD_BYTES: int = int(
    os.environ.get("TRANSMAX_MAX_UPLOAD_BYTES", str(50 * 1024 * 1024))
)


# Magic-byte prefixes per supported extension. The first N bytes of a valid
# file MUST start with one of these prefixes. TXT is special-cased below.
MAGIC_SIGNATURES: dict[str, list[bytes]] = {
    ".pdf": [b"%PDF-"],
    ".docx": [b"PK\x03\x04"],  # ZIP container — TMX-3706 will deepen this check
}


# How many bytes we sniff at the start. Larger = better TXT validation; smaller
# = faster reject path. 4KB is enough for both magic and TXT NUL-byte heuristics.
SNIFF_BYTES = 4096


class FileValidationError(HTTPException):
    """400 with a structured detail describing the failure category."""

    def __init__(self, category: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(
            status_code=status_code,
            detail={"category": category, "message": message},
        )


def _is_valid_magic(prefix: bytes, allowed_extensions: Iterable[str]) -> Optional[str]:
    """Return the extension whose magic matches, or None."""
    for ext in allowed_extensions:
        for sig in MAGIC_SIGNATURES.get(ext, []):
            if prefix.startswith(sig):
                return ext
    return None


def _is_plausibly_text(prefix: bytes) -> bool:
    """Heuristic: the prefix decodes as UTF-8/Latin-1 and has no NUL bytes."""
    if b"\x00" in prefix:
        return False
    try:
        prefix.decode("utf-8")
        return True
    except UnicodeDecodeError:
        pass
    try:
        prefix.decode("latin-1")
        return True
    except UnicodeDecodeError:
        return False


def emit_av_scan_request(path: str, metadata: Optional[dict] = None) -> None:
    """
    AV scan trigger. Logs a structured event today; TMX-3707 wires clamd.

    The structured-log shape is the source of truth for the deployment-side
    handler — keep keys stable.
    """
    payload = {
        "event": "av_scan.requested",
        "path": path,
        "size_bytes": Path(path).stat().st_size if Path(path).exists() else None,
    }
    if metadata:
        payload.update(metadata)
    logger.info("AV_SCAN_REQUEST | %s", payload)


async def validate_and_save_upload(
    upload_file: UploadFile,
    dest_path: str,
    allowed_extensions: Iterable[str],
    av_metadata: Optional[dict] = None,
) -> int:
    """
    Validate magic bytes, save with size cap, fire AV trigger.

    Returns the validated byte count on success. Raises `FileValidationError`
    (HTTPException 400) on any rejection. On rejection the partially-written
    destination file is deleted before the exception propagates.

    Strategy is a single streaming pass:
      1. Read SNIFF_BYTES of prefix
      2. Validate magic / text-shape against allowed_extensions
      3. Write the prefix, then continue streaming chunks while tracking
         running total against MAX_UPLOAD_BYTES
      4. On any rejection, delete the partial file and raise
    """
    allowed = tuple(e.lower() for e in allowed_extensions)
    filename_ext = Path(upload_file.filename or "").suffix.lower()

    if filename_ext not in allowed:
        raise FileValidationError(
            "unsupported_extension",
            f"Filename extension {filename_ext!r} not in allowed {allowed!r}.",
        )

    # Read the prefix to sniff.
    prefix = await upload_file.read(SNIFF_BYTES)

    # Magic-byte / text-shape check.
    if filename_ext == ".txt":
        if not prefix:
            raise FileValidationError("empty_file", "Empty file uploaded.")
        if not _is_plausibly_text(prefix):
            raise FileValidationError(
                "magic_byte_mismatch",
                "Filename ends with .txt but content is not valid text "
                "(binary / NUL bytes detected).",
            )
    else:
        sniffed_ext = _is_valid_magic(prefix, allowed_extensions=(filename_ext,))
        if sniffed_ext is None:
            raise FileValidationError(
                "magic_byte_mismatch",
                f"Filename {upload_file.filename!r} ends with {filename_ext!r} but "
                f"file content does not match expected magic bytes.",
            )

    # Stream remaining bytes to disk under the size cap.
    total_bytes = 0
    written = False
    try:
        async with aiofiles.open(dest_path, "wb") as out_file:
            await out_file.write(prefix)
            total_bytes += len(prefix)
            written = True
            while True:
                chunk = await upload_file.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    # Stop here; cleanup happens in finally.
                    raise FileValidationError(
                        "file_too_large",
                        f"Upload exceeded {MAX_UPLOAD_BYTES} bytes "
                        f"(stopped at {total_bytes}).",
                    )
                await out_file.write(chunk)
    except FileValidationError:
        if written and Path(dest_path).exists():
            try:
                os.remove(dest_path)
            except OSError as exc:
                logger.warning("Failed to clean partial upload %s: %s", dest_path, exc)
        raise
    except Exception:
        if written and Path(dest_path).exists():
            try:
                os.remove(dest_path)
            except OSError:
                pass
        raise

    # AV trigger after successful save.
    md = dict(av_metadata or {})
    md.setdefault("filename", upload_file.filename)
    md.setdefault("declared_extension", filename_ext)
    emit_av_scan_request(dest_path, md)

    return total_bytes
