"""
TMX-BB-SYNTH — load the synthetic "Veridian Therapeutics" black book.

The dataset (``scripts/black_book/veridian_blackbook.json``) is near-real
SYNTHETIC pharma knowledge for a FICTIONAL company: EMA QRD glossary terms,
forbidden/deprecated terminology, and regulatory translation rules across
en→fr, en→de, en→es. It exists to demonstrate the Black Book's power in
translation activities (term enforcement, forbidden-term blocking, rule firing)
without shipping any real customer data.

This module is import-safe (pure helpers + a guarded ``main()``) so the dataset
integrity and the idempotent seed are both unit-tested. Seeding is tenant-scoped
(A1/A4): every row hangs off a Veridian organization, and all DB access runs
inside an ``org_context``.

CLI:
    python scripts/seed_synthetic_black_book.py            # seed default local DB
    python scripts/seed_synthetic_black_book.py --org-id <uuid>
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict

logger = logging.getLogger("synthetic_black_book")

DATA_PATH = Path(__file__).resolve().parent / "black_book" / "veridian_blackbook.json"


def load_blackbook(path: Path = DATA_PATH) -> dict:
    """Read and validate the synthetic dataset. Raises on any integrity defect."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    validate_blackbook(data)
    return data


def validate_blackbook(data: dict) -> None:
    """Fail loud (A3) on a malformed dataset — a silent half-load would seed a
    misleading demo that claims coverage it does not have."""
    if not isinstance(data.get("org"), dict) or not data["org"].get("org_slug"):
        raise ValueError("black book: missing org.org_slug")

    glossaries = data.get("glossaries")
    if not isinstance(glossaries, list) or not glossaries:
        raise ValueError("black book: no glossaries")

    for g in glossaries:
        for field in (
            "glossary_id",
            "version",
            "source_language",
            "target_language",
            "terms",
        ):
            if field not in g:
                raise ValueError(f"glossary missing '{field}': {g.get('glossary_id')}")
        seen_term_ids: set = set()
        seen_sources: set = set()
        for t in g["terms"]:
            for field in ("term_id", "source_text", "target_text", "is_forbidden"):
                if field not in t:
                    raise ValueError(f"term missing '{field}' in {g['glossary_id']}")
            if t["term_id"] in seen_term_ids:
                raise ValueError(
                    f"duplicate term_id {t['term_id']} in {g['glossary_id']}"
                )
            if t["source_text"] in seen_sources:
                raise ValueError(
                    f"duplicate source_text {t['source_text']!r} in {g['glossary_id']}"
                )
            seen_term_ids.add(t["term_id"])
            seen_sources.add(t["source_text"])

    rules = data.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("black book: no rules")
    seen_rule_ids: set = set()
    for r in rules:
        for field in (
            "rule_id",
            "source_pattern",
            "target_correction",
            "source_language",
            "target_language",
        ):
            if field not in r:
                raise ValueError(f"rule missing '{field}': {r.get('rule_id')}")
        if r["rule_id"] in seen_rule_ids:
            raise ValueError(f"duplicate rule_id {r['rule_id']}")
        seen_rule_ids.add(r["rule_id"])


def ensure_org(session, org_meta: dict) -> str:
    """Find-or-create the Veridian organization (NOT tenant-scoped). Returns id."""
    from app.models.database import Organization

    slug = str(org_meta["org_slug"])
    existing = session.query(Organization).filter(Organization.slug == slug).first()
    if existing is not None:
        return str(existing.id)

    org = Organization(
        name=str(org_meta.get("name", slug)),
        slug=slug,
        org_kind="customer",
        metadata_json={"synthetic": True, "source": "veridian_blackbook"},
    )
    session.add(org)
    session.commit()
    logger.info("Created synthetic org %s (%s)", org.name, org.id)
    return str(org.id)


def seed_blackbook(session, org_id: str, data: dict) -> Dict[str, int]:
    """Idempotently upsert glossaries, terms, and rules for ``org_id``.

    Idempotency keys: Glossary PK (glossary_id, version); GlossaryTerm by
    (glossary_id, version, source_text); TranslationRule by rule_id PK.
    Returns counts of rows created this run.
    """
    from app.core.tenant_context import org_context
    from app.models.models import Glossary, GlossaryTerm, TranslationRule

    counts = {"glossaries": 0, "terms": 0, "rules": 0}

    with org_context(org_id):
        for g in data["glossaries"]:
            exists = (
                session.query(Glossary)
                .filter(
                    Glossary.glossary_id == g["glossary_id"],
                    Glossary.version == g["version"],
                )
                .first()
            )
            if exists is None:
                session.add(
                    Glossary(
                        glossary_id=g["glossary_id"],
                        version=g["version"],
                        organization_id=org_id,
                        is_active=True,
                        meta_json={
                            "source_language": g["source_language"],
                            "target_language": g["target_language"],
                            "domain": g.get("domain", "pharma"),
                            "synthetic": True,
                        },
                    )
                )
                counts["glossaries"] += 1

            for t in g["terms"]:
                term_exists = (
                    session.query(GlossaryTerm)
                    .filter(
                        GlossaryTerm.glossary_id == g["glossary_id"],
                        GlossaryTerm.glossary_version == g["version"],
                        GlossaryTerm.source_text == t["source_text"],
                    )
                    .first()
                )
                if term_exists is not None:
                    continue
                session.add(
                    GlossaryTerm(
                        organization_id=org_id,
                        glossary_id=g["glossary_id"],
                        glossary_version=g["version"],
                        term_id=t["term_id"],
                        source_text=t["source_text"],
                        target_text=t["target_text"],
                        is_forbidden=bool(t["is_forbidden"]),
                        allowed_variants=t.get("allowed_variants", []),
                        metadata_json={
                            "category": t.get("category"),
                            "note": t.get("note"),
                        },
                    )
                )
                counts["terms"] += 1

        for r in data["rules"]:
            rule_exists = (
                session.query(TranslationRule)
                .filter(TranslationRule.rule_id == r["rule_id"])
                .first()
            )
            if rule_exists is not None:
                continue
            session.add(
                TranslationRule(
                    rule_id=r["rule_id"],
                    organization_id=org_id,
                    source_pattern=r["source_pattern"],
                    target_correction=r["target_correction"],
                    source_language=r["source_language"],
                    target_language=r["target_language"],
                    context_tag=r.get("context_tag", "general"),
                    domain=r.get("domain", "pharma"),
                    is_regex=bool(r.get("is_regex", False)),
                    is_strict=bool(r.get("is_strict", False)),
                    priority=int(r.get("priority", 0)),
                    description=r.get("description"),
                    confidence_score=1.0,
                    status="ACTIVE",
                    origin_event_id="SEED_VERIDIAN_V1",
                )
            )
            counts["rules"] += 1

        session.commit()

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the synthetic Veridian black book."
    )
    parser.add_argument("--org-id", default=None, help="Existing org id to seed into.")
    parser.add_argument("--db-url", default=None, help="Override DATABASE_URL.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    if args.db_url:
        os.environ["DATABASE_URL"] = args.db_url

    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from app.core.database import SessionLocal, init_db

    init_db()
    data = load_blackbook()
    session = SessionLocal()
    try:
        org_id = args.org_id or ensure_org(session, data["org"])
        counts = seed_blackbook(session, org_id, data)
        logger.info("Seeded synthetic black book into org %s: %s", org_id, counts)
    finally:
        session.close()


if __name__ == "__main__":
    main()
