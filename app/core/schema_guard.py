"""Boot-time schema-drift guard (TMX-DEPLOY-1).

The deploy path runs ``create_all`` (via ``init_db``), which creates *missing*
tables but NEVER adds new columns to a table that already exists. On a
persisted database that predates a model change, the new columns are simply
absent — and every ``SELECT`` that names them 500s at runtime (e.g. the
2026-06 Railway incident: ``column documents.organization_id does not exist``).

This module turns that silent, user-facing failure into a loud boot-time one:
after ``create_all`` runs, we compare every model column against the live DB
and refuse to start (or log CRITICAL) if any are missing. An operator sees the
problem at deploy time and reseeds/migrates, instead of users hitting 500s.

Scope: we only flag columns of tables that ACTUALLY EXIST in the DB. A table
absent from the engine (e.g. a pgvector-only regulatory table on SQLite, which
``init_db`` intentionally skips) is NOT drift — it was never meant to be here.
This avoids false positives from the A4 dual-model-layer split.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class SchemaDriftError(RuntimeError):
    """Raised at boot when the live DB is missing columns the models declare."""


def find_schema_drift(engine) -> list[str]:
    """Return ``["table.column", ...]`` for model columns missing in the live DB.

    Only inspects tables that exist in the database; absent tables are skipped
    (they were intentionally not created on this engine). Read-only.
    """
    from sqlalchemy import inspect as sa_inspect

    from app.models.database import Base

    insp = sa_inspect(engine)
    existing_tables = set(insp.get_table_names())

    missing: list[str] = []
    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue  # not created on this engine (e.g. pgvector-only on SQLite)
        db_cols = {c["name"] for c in insp.get_columns(table_name)}
        for col in table.columns:
            if col.name not in db_cols:
                missing.append(f"{table_name}.{col.name}")
    return missing


def assert_schema_current(engine, *, allow_drift: bool = False) -> list[str]:
    """Fail loud (or warn) if the live schema is missing model columns.

    Args:
        engine: the SQLAlchemy engine to inspect.
        allow_drift: if True, log CRITICAL instead of raising — an emergency
            escape hatch (set ``ALLOW_SCHEMA_DRIFT=1``) for booting a known-
            drifted DB while a migration/reseed is prepared.

    Returns:
        The drift list (empty when the schema is current).

    Raises:
        SchemaDriftError: when drift is found and ``allow_drift`` is False.
    """
    drift = find_schema_drift(engine)
    if not drift:
        return drift

    msg = (
        "Schema drift detected — the live database is missing model columns. "
        "This deploy ran create_all on a persisted DB without migrating. "
        f"Missing ({len(drift)}): {', '.join(sorted(drift))}. "
        "Run migrations or reseed the schema (e.g. DROP SCHEMA public CASCADE; "
        "CREATE SCHEMA public; then restart). See TMX-DEPLOY-1."
    )
    if allow_drift:
        logger.critical("%s [ALLOW_SCHEMA_DRIFT set — booting anyway]", msg)
        return drift
    raise SchemaDriftError(msg)
