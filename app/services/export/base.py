"""
TMX-EXPORT-1 — export protocol + canonical value objects (ADR-0006).

These types are backend-agnostic. A ``LayoutBlock`` is the generic unit every
backend reasons about (text + geometry + style); the intelligence services
(classify / fonts / layout) consume it without knowing the source format, and the
``FidelityReport`` is how a backend is honest about what it could and could not
preserve (A3 — degrade loud, never silently ship a degraded artefact).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Protocol, runtime_checkable

# A translator is injected, never imported, so backends stay testable and the
# translation/quality separation (A2) holds: this maps source strings -> target
# strings in order. The default production wiring goes through app/services/llm.
TranslateFn = Callable[[list[str]], list[str]]


class Translatability(str, Enum):
    """What the renderer should DO with a block — a classification, not a source rule."""

    CONTENT = "content"      # translate + re-render in place
    PRESERVE = "preserve"    # leave the source glyphs untouched (branding, running
    #                          heads, folios, identifiers) — exact preservation
    DROP_CAP = "drop_cap"    # decorative initial; re-seat from its body paragraph


class FitStrategy(str, Enum):
    """How a translated box was made to fit — recorded per block for the report."""

    IN_PLACE = "in_place"    # fits at the source size
    SHRUNK = "shrunk"        # font shrunk to fit the source box
    REFLOWED = "reflowed"    # box grown downward within the page to fit
    ESCALATE = "escalate"    # could not fit acceptably — flagged for Tier-2 / review


@dataclass(frozen=True)
class LayoutBlock:
    """A generic text block + geometry + dominant style. Format-agnostic."""

    block_id: str
    text: str
    bbox: tuple[float, float, float, float]            # x0, y0, x1, y1
    line_bboxes: tuple[tuple[float, float, float, float], ...]
    font_name: str
    size: float
    color: int                                         # 0xRRGGBB
    page_index: int
    page_width: float
    page_height: float

    @property
    def char_height_ratio(self) -> float:
        return self.size / self.page_height if self.page_height else 0.0


@dataclass
class BlockVerdict:
    """The per-block record that makes the export auditable (A1 spirit)."""

    block_id: str
    page_index: int
    translatability: Translatability
    strategy: Optional[FitStrategy] = None
    font_substituted: bool = False
    fitted_size: Optional[float] = None
    overflow: bool = False
    note: str = ""


@dataclass
class FidelityReport:
    """Document-level honesty: what was translated, preserved, or degraded."""

    backend: str
    source_filename: str
    target_lang: str
    verdicts: list[BlockVerdict] = field(default_factory=list)

    @property
    def block_count(self) -> int:
        return len(self.verdicts)

    @property
    def degraded(self) -> bool:
        """True if any block could not be rendered faithfully (overflow/escalate)."""
        return any(
            v.overflow or v.strategy is FitStrategy.ESCALATE for v in self.verdicts
        )

    def summary(self) -> dict:
        by_class: dict[str, int] = {}
        by_strategy: dict[str, int] = {}
        for v in self.verdicts:
            by_class[v.translatability.value] = by_class.get(v.translatability.value, 0) + 1
            if v.strategy:
                by_strategy[v.strategy.value] = by_strategy.get(v.strategy.value, 0) + 1
        return {
            "backend": self.backend,
            "source": self.source_filename,
            "target_lang": self.target_lang,
            "blocks": self.block_count,
            "by_translatability": by_class,
            "by_strategy": by_strategy,
            "font_substitutions": sum(1 for v in self.verdicts if v.font_substituted),
            "degraded": self.degraded,
            "degraded_blocks": [v.block_id for v in self.verdicts
                                if v.overflow or v.strategy is FitStrategy.ESCALATE],
        }


@dataclass
class ExportResult:
    data: bytes
    media_type: str
    fidelity: FidelityReport


class ExportError(Exception):
    """Base class for export failures."""


class ExporterUnavailable(ExportError):
    """The requested backend cannot run here (missing lib/dep).

    A3: a backend that cannot run MUST fail loud, never silently fall back to a
    worse exporter that ships a degraded regulatory artefact.
    """


@runtime_checkable
class DocumentExporter(Protocol):
    """Protocol every export backend implements."""

    name: str

    def supports(self, file_ext: str) -> bool:
        """True if this backend can export from the given source extension."""
        ...

    def export(self, source_path: str, translate_fn: "TranslateFn",
               target_lang: str) -> ExportResult:
        """Produce a translated artefact + a fidelity report. Raise
        ExporterUnavailable if the backend cannot run here."""
        ...
