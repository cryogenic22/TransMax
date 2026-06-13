"""
TMX-EXPORT-1 — fit/strategy negotiation (ADR-0006 AC-5).

Translated text expands (FR ~+15-20%, DE more) and a fixed PDF box will not hold
it at the source size. Rather than clip silently, the renderer NEGOTIATES, in
order of decreasing fidelity, and records which rung it landed on:

    IN_PLACE  -> fits at source size
    SHRUNK    -> shrink down to a readability floor
    REFLOWED  -> grow the box downward within the page to fit at the floor
    ESCALATE  -> still won't fit; flag the block for Tier-2 re-render / review

The text-measuring function is injected so this module is unit-testable without
a real PDF engine (the overlay backend passes a fitz-backed measurer).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from app.services.export.base import FitStrategy

# measure(text, width, height, fontname, fontfile, size) -> leftover vertical space.
# >= 0 means the text fit; < 0 means it overflowed (PyMuPDF insert_textbox semantics).
MeasureFn = Callable[[str, float, float, str, "Optional[str]", float], float]


@dataclass(frozen=True)
class FitResult:
    strategy: FitStrategy
    fontsize: float
    rect: tuple[float, float, float, float]   # possibly grown downward
    overflow: bool


def negotiate(
    text: str,
    bbox: tuple[float, float, float, float],
    fontname: str,
    fontfile: Optional[str],
    source_size: float,
    page_height: float,
    measure: MeasureFn,
    *,
    min_floor: float = 5.0,
    shrink_ratio: float = 0.6,
    bottom_margin: float = 36.0,
    step: float = 0.5,
) -> FitResult:
    """Find the highest-fidelity way to fit ``text`` into ``bbox``."""
    x0, y0, x1, y1 = bbox
    width = x1 - x0
    height = y1 - y0
    floor = max(min_floor, source_size * shrink_ratio)

    # Rung 1: in place at source size.
    if measure(text, width, height, fontname, fontfile, source_size) >= 0:
        return FitResult(FitStrategy.IN_PLACE, source_size, bbox, overflow=False)

    # Rung 2: shrink toward the floor.
    size = source_size - step
    while size >= floor:
        if measure(text, width, height, fontname, fontfile, size) >= 0:
            return FitResult(FitStrategy.SHRUNK, size, bbox, overflow=False)
        size -= step

    # Rung 3: reflow — grow the box downward (bounded by the page) at the floor.
    max_y1 = page_height - bottom_margin
    if y1 < max_y1:
        grown = (x0, y0, x1, max_y1)
        if measure(text, width, max_y1 - y0, fontname, fontfile, floor) >= 0:
            return FitResult(FitStrategy.REFLOWED, floor, grown, overflow=False)

    # Rung 4: escalate — cannot fit acceptably. Render best-effort at the floor,
    # flagged so the FidelityGate surfaces it (A3).
    return FitResult(FitStrategy.ESCALATE, floor, bbox, overflow=True)
