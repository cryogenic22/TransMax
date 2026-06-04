"""TMX-ROUTER-3 — per-tenant routing policy: storage, RBAC, validation, override."""
from __future__ import annotations

import pytest

from app.auth.permissions import UserRole
from app.core.model_registry import select_model
from app.models.database import DEFAULT_ORG_ID
from app.services.routing_policy_service import (
    get_policy_overrides,
    upsert_policy,
    validate_overrides,
)


# --- validation (pure) -----------------------------------------------------


def test_validate_overrides_ok():
    validate_overrides({"translate:high": "frontier", "detect:low": "cheap"})


def test_validate_overrides_rejects_bad_key():
    with pytest.raises(ValueError):
        validate_overrides({"translate": "frontier"})       # no complexity
    with pytest.raises(ValueError):
        validate_overrides({"bogus:high": "frontier"})       # unknown task


def test_validate_overrides_rejects_bad_tier():
    with pytest.raises(ValueError):
        validate_overrides({"translate:high": "supreme"})    # unknown tier


# --- select_model honours overrides (pure) ---------------------------------


def test_select_model_applies_override():
    # translate:high is frontier (gpt-4o) by default; override it to cheap.
    assert select_model("translate", "high", policy_overrides={"translate:high": "cheap"}) == "gpt-4o-mini"
    # An invalid override is ignored → default policy (frontier).
    assert select_model("translate", "high", policy_overrides={"translate:high": "bogus"}) == "gpt-4o"
    # Unrelated override doesn't affect this key.
    assert select_model("translate", "high", policy_overrides={"detect:low": "frontier"}) == "gpt-4o"


# --- service: RBAC + storage round-trip ------------------------------------


def test_upsert_requires_permission(fresh_engine_for_db):
    db = fresh_engine_for_db.SessionLocal()
    try:
        with pytest.raises(PermissionError):
            upsert_policy(
                DEFAULT_ORG_ID, {"translate:high": "cheap"}, True,
                "u1", UserRole.TRANSLATOR, db=db,
            )
    finally:
        db.close()


def test_upsert_and_get_roundtrip(fresh_engine_for_db):
    db = fresh_engine_for_db.SessionLocal()
    try:
        upsert_policy(
            DEFAULT_ORG_ID, {"translate:high": "cheap"}, True,
            "admin1", UserRole.ADMIN, db=db,
        )
        assert get_policy_overrides(DEFAULT_ORG_ID, db) == {"translate:high": "cheap"}

        # Update + disable ⇒ overrides no longer applied.
        upsert_policy(
            DEFAULT_ORG_ID, {"translate:high": "cheap"}, False,
            "admin1", UserRole.ADMIN, db=db,
        )
        assert get_policy_overrides(DEFAULT_ORG_ID, db) == {}
    finally:
        db.close()


def test_get_overrides_empty_when_no_row(fresh_engine_for_db):
    db = fresh_engine_for_db.SessionLocal()
    try:
        assert get_policy_overrides(DEFAULT_ORG_ID, db) == {}
    finally:
        db.close()
