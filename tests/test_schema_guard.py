"""TMX-DEPLOY-1 — boot-time schema-drift guard.

Reproduces the 2026-06 Railway incident in miniature: a persisted DB missing a
model column (create_all can't ALTER it in) must be caught LOUDLY at boot, not
served as a runtime 500.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.core.schema_guard import (
    SchemaDriftError,
    assert_schema_current,
    find_schema_drift,
)


def test_no_drift_on_fresh_schema(fresh_engine_for_db):
    """A schema built by create_all has every model column — no drift."""
    assert find_schema_drift(fresh_engine_for_db.engine) == []
    # assert_schema_current is a no-op (returns empty) on a current schema.
    assert assert_schema_current(fresh_engine_for_db.engine) == []


def test_detects_missing_column_and_raises(fresh_engine_for_db):
    """A column present in the model but dropped from the DB is flagged, and
    assert_schema_current fails loud (the incident: documents.organization_id)."""
    eng = fresh_engine_for_db.engine
    with eng.begin() as conn:
        conn.execute(text("ALTER TABLE documents DROP COLUMN total_tokens"))

    drift = find_schema_drift(eng)
    assert "documents.total_tokens" in drift

    with pytest.raises(SchemaDriftError) as exc:
        assert_schema_current(eng)
    assert "documents.total_tokens" in str(exc.value)


def test_allow_drift_downgrades_to_warning(fresh_engine_for_db):
    """The ALLOW_SCHEMA_DRIFT escape hatch returns the drift without raising."""
    eng = fresh_engine_for_db.engine
    with eng.begin() as conn:
        conn.execute(text("ALTER TABLE documents DROP COLUMN total_cost_usd"))

    drift = assert_schema_current(eng, allow_drift=True)
    assert "documents.total_cost_usd" in drift  # returned, not raised


def test_absent_table_is_not_drift(fresh_engine_for_db):
    """A model table not present in the DB (e.g. pgvector-only on SQLite, which
    init_db intentionally skips) is NOT reported as drift — only missing
    columns of tables that exist."""
    eng = fresh_engine_for_db.engine
    with eng.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS documents"))
    drift = find_schema_drift(eng)
    # documents no longer exists, so none of its columns are flagged.
    assert not any(d.startswith("documents.") for d in drift)
