"""
TMX-EXPORT-1 — figure-region rasteriser (ADR-0006, Tier-2 figure recovery).

Renders a sub-region of a source PDF page to a PNG using ``pypdfium2`` (Apache-2.0,
Google's PDFium — permissive, NOT PyMuPDF). Tier-2 re-render uses this to recover
figures: the IR carries each figure's bbox; we rasterise that exact region from the
original so charts/images come back faithfully (everything is rendered, including
vector art), instead of dropping them to a placeholder.

Coordinate handling: PDFium page space is points, origin bottom-left, y up.
``render(crop=(left, bottom, right, top))`` insets from each page edge. We normalise
the IR bbox (which may be TOP-LEFT origin per Docling) into that frame.
"""
from __future__ import annotations

from typing import Optional


def is_available() -> bool:
    try:
        import pypdfium2  # noqa: F401
        return True
    except ImportError:
        return False


def render_region(
    source_path: str,
    page_no: int,
    bbox: tuple[float, float, float, float],
    *,
    coord_origin: Optional[str] = None,
    pad: float = 2.0,
    scale: float = 2.0,
) -> Optional[bytes]:
    """Rasterise the page region at ``bbox`` to PNG bytes, or None if unavailable.

    ``page_no`` is 1-based (Docling convention). ``bbox`` = (l, t, r, b) in points.
    """
    try:
        import io

        import pypdfium2 as pdfium
    except ImportError:
        return None
    try:
        pdf = pdfium.PdfDocument(source_path)
        idx = max(0, (page_no or 1) - 1)
        if idx >= len(pdf):
            return None
        page = pdf[idx]
        W, H = page.get_size()
        l, t, r, b = bbox

        # Normalise to bottom-left / y-up.
        origin = (coord_origin or "").upper()
        if "TOP" in origin:                 # TOPLEFT: y measured from the top
            y_top, y_bottom = H - t, H - b
        else:                                # BOTTOMLEFT (PDFium native)
            y_top, y_bottom = max(t, b), min(t, b)
        x_left, x_right = min(l, r), max(l, r)

        crop = (
            max(0.0, x_left - pad),          # left inset
            max(0.0, y_bottom - pad),        # bottom inset
            max(0.0, W - x_right - pad),     # right inset
            max(0.0, H - y_top - pad),       # top inset
        )
        if (W - crop[0] - crop[2]) <= 1 or (H - crop[1] - crop[3]) <= 1:
            return None                      # degenerate region

        bitmap = page.render(scale=scale, crop=crop)
        pil = bitmap.to_pil()
        out = io.BytesIO()
        pil.save(out, format="PNG")
        pdf.close()
        return out.getvalue()
    except Exception:  # noqa: BLE001 — figure recovery is best-effort; caller degrades
        return None
