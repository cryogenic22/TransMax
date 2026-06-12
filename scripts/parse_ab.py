"""
TMX-PARSE-1 — opt-in A/B of parser backends on a real document.

Usage:
    python scripts/parse_ab.py "<path-to.pdf>" [--backends pypdf,docling] [--out report.md]

Runs each backend through the canonical IR and reports the structural delta
(element-type histogram, table/figure counts, unicode sanity). NOT part of the
unit suite — Docling pulls models and can take minutes on first run.
"""
from __future__ import annotations

import argparse
import sys
import time

from app.services.parsing import ParserError, get_parser


def _run(backend: str, path: str):
    t = time.time()
    try:
        doc = get_parser(backend).parse(path)
    except ParserError as exc:
        return {"backend": backend, "error": f"{type(exc).__name__}: {exc}"}
    dt = time.time() - t
    tables = sum(1 for b in doc.blocks if b.element_type.value == "table")
    figures = sum(1 for b in doc.blocks if b.element_type.value == "figure")
    text = " ".join(b.text for b in doc.blocks)
    return {
        "backend": backend,
        "seconds": round(dt, 1),
        "blocks": len(doc.blocks),
        "pages": doc.page_count,
        "tables": tables,
        "figures": figures,
        "histogram": doc.structure_histogram(),
        # mojibake heuristic: U+FFFD replacement char present?
        "has_mojibake": "�" in text,
        "sample": text[:200],
    }


def _fmt(r: dict) -> str:
    if "error" in r:
        return f"### {r['backend']}\n\n**unavailable** — {r['error']}\n"
    hist = "\n".join(f"  - {k}: {v}" for k, v in sorted(r["histogram"].items()))
    return (
        f"### {r['backend']}\n\n"
        f"- time: {r['seconds']}s · pages: {r['pages']} · blocks: {r['blocks']}\n"
        f"- **tables: {r['tables']} · figures: {r['figures']}**\n"
        f"- mojibake (U+FFFD): {r['has_mojibake']}\n"
        f"- element-type histogram:\n{hist}\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--backends", default="pypdf,docling")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    backends = [b.strip() for b in args.backends.split(",") if b.strip()]
    results = [_run(b, args.pdf) for b in backends]
    report = f"# Parser A/B — `{args.pdf}`\n\n" + "\n".join(_fmt(r) for r in results)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(report)
        print(f"wrote {args.out}")
    # ASCII-safe console summary (avoids Windows cp1252 encode errors)
    for r in results:
        if "error" in r:
            print(f"{r['backend']:8s}  UNAVAILABLE  {r['error'][:60]}")
        else:
            print(
                f"{r['backend']:8s}  {r['seconds']:>6}s  blocks={r['blocks']:<4} "
                f"tables={r['tables']:<3} figures={r['figures']:<3} "
                f"types={len(r['histogram'])} mojibake={r['has_mojibake']}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
