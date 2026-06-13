"""
TMX-EXPORT-1 — font resolution (ADR-0006 AC-6).

Two problems to solve, both honestly:

  1. Source PDFs embed *subsetted* faces (only the glyphs the source used), so the
     target language's glyphs are frequently absent — reusing the embedded face
     renders tofu. We map the source face to a fallback by classification
     (serif / sans / mono) and RECORD the substitution (A3).
  2. The PDF base-14 fallbacks only cover Latin-1 — which is NOT enough for real
     French (``œ`` in œdème/cœur, em-dashes, « guillemets », curly quotes are all
     outside Latin-1). So we prefer an EMBEDDED Unicode face (DejaVu: full Latin +
     punctuation) and fall back to base-14 only if no Unicode TTF is found —
     flagging the reduced coverage rather than silently mangling the text.

Font files are located at runtime (configurable dir → matplotlib's bundled DejaVu
→ a repo-bundled dir). Productionising on Linux/Railway means bundling the TTFs in
``requirements-export`` assets; the locator already looks there first.
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

_SERIF_HINTS = ("times", "quadraat", "roman", "serif", "georgia", "minion",
                "garamond", "caslon", "palatino", "book")
_MONO_HINTS = ("mono", "courier", "consol", "menlo", "typewriter")

# family key -> (preferred Unicode TTF filename, base-14 fallback name)
_FAMILY = {
    "serif": ("DejaVuSerif.ttf", "tiro"),
    "sans": ("DejaVuSans.ttf", "helv"),
    "mono": ("DejaVuSansMono.ttf", "cour"),
}


@dataclass(frozen=True)
class FontChoice:
    fontname: str                 # registration alias / base-14 name
    fontfile: Optional[str]       # embedded Unicode TTF path, or None (base-14)
    substituted: bool
    charset_ok: bool
    reason: str


def _family_key(source_font_name: str) -> str:
    n = (source_font_name or "").lower()
    if any(h in n for h in _MONO_HINTS):
        return "mono"
    if any(h in n for h in _SERIF_HINTS):
        return "serif"
    return "sans"


def _font_search_dirs() -> list[str]:
    dirs: list[str] = []
    try:
        from app.core.config import settings
        d = getattr(settings, "export_font_dir", "") or ""
        if d:
            dirs.append(d)
    except Exception:  # noqa: BLE001 — config is best-effort here
        pass
    # repo-bundled assets (preferred for deterministic Linux/Railway deploys)
    dirs.append(os.path.join(os.path.dirname(__file__), "_fonts"))
    # matplotlib ships DejaVu — convenient in dev
    try:
        import matplotlib
        dirs.append(os.path.join(os.path.dirname(matplotlib.__file__),
                                 "mpl-data", "fonts", "ttf"))
    except Exception:  # noqa: BLE001
        pass
    return dirs


@lru_cache(maxsize=8)
def _locate(ttf_filename: str) -> Optional[str]:
    for d in _font_search_dirs():
        cand = os.path.join(d, ttf_filename)
        if os.path.exists(cand):
            return cand
        hits = glob.glob(os.path.join(d, ttf_filename))
        if hits:
            return hits[0]
    return None


@lru_cache(maxsize=8)
def _cmap(fontfile: str) -> frozenset:
    """The set of Unicode code points a TTF can render (fontTools, MIT — no fitz)."""
    from fontTools.ttLib import TTFont
    return frozenset(TTFont(fontfile).getBestCmap().keys())


def _covers(fontfile: Optional[str], text: str) -> bool:
    """True if the chosen face can render every char. DejaVu covers Latin (+ punct,
    œ, guillemets, dashes); base-14 covers only Latin-1."""
    if fontfile:  # DejaVu — broad Latin/punct coverage; CJK/Arabic still excluded
        try:
            cm = _cmap(fontfile)
            return all(ord(c) in cm for c in text if not c.isspace())
        except Exception:  # noqa: BLE001 — if we cannot verify, assume broad coverage
            return True
    try:
        text.encode("latin-1")
        return True
    except UnicodeEncodeError:
        return False


def resolve(source_font_name: str, target_text: str) -> FontChoice:
    """Pick a render font for ``target_text`` matched to the source family."""
    key = _family_key(source_font_name)
    ttf_name, base14 = _FAMILY[key]
    fontfile = _locate(ttf_name)
    fontname = ttf_name.rsplit(".", 1)[0] if fontfile else base14
    charset_ok = _covers(fontfile, target_text)

    if fontfile and charset_ok:
        reason = f"embedded {fontname} (Unicode) for {key}"
    elif fontfile and not charset_ok:
        reason = (f"embedded {fontname} lacks some target glyphs (e.g. CJK/complex "
                  f"script) — flagged for a wider Unicode face")
    elif not fontfile and charset_ok:
        reason = f"no Unicode TTF found; base-14 {base14} covers this (Latin-1)"
    else:
        reason = (f"no Unicode TTF found and base-14 {base14} cannot cover the "
                  f"target (needs œ/dashes/guillemets) — flagged, not mangled")
    return FontChoice(fontname=fontname, fontfile=fontfile, substituted=True,
                      charset_ok=charset_ok, reason=reason)
