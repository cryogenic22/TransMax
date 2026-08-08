"""
Shared test fixtures for TransMax.

TMX-AUDIT-CLEANUP-ROUTES: `fresh_engine_for_db` swaps `app.core.database`
engine + SessionLocal in-place to a tmp SQLite DB, instead of using
`importlib.reload(core_db)`. The reload approach creates NEW function
objects (e.g. `get_db`), which breaks dependency overrides in any other
test that does `app.dependency_overrides[get_db] = mock` — those overrides
key off the NEW function object but the routes captured the OLD one at
import time, so the override never applies and the route hits a real
session. Symptom: `pytest tests/X` passes in isolation, fails in the full
suite with 404s on routes that look correctly registered.

In-place swap preserves function identity. `get_db` is a generator that
reads `SessionLocal` at call time (not at definition time), so swapping
the module-level `SessionLocal` is sufficient.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture(autouse=True)
def _hermetic_llm(monkeypatch):
    """Make the whole suite hermetic — no test may depend on a real provider
    credential or reach the network.

    Root cause this closes: `TranslationEngine.__init__` eagerly builds an LLM
    via `get_llm(task="translate")`, and `settings.enable_live_llm_inference`
    defaults to ``True`` while `settings.openai_api_key` defaults to ``None``.
    So on a clean clone (no private ``.env``) merely *constructing* the engine
    raised ``openai.OpenAIError: Missing credentials`` — the 14 CI failures on
    PR #22 — and, worse, a run WITH a key made real, paid, non-deterministic
    provider calls (the local suite took ~8 min for exactly this reason).

    The app already ships the offline path: `get_llm` returns a deterministic
    fake model when `enable_live_llm_inference` is False. Nothing turned it on
    for tests. This autouse fixture selects that path by default and injects a
    dummy key so client construction can never fail. A test that specifically
    exercises the live-provider wiring re-enables it in its own body (and owns
    its own mock), so this default does not constrain those.
    """
    from app.core.config import settings
    from app.services import llm as llm_module
    import app.agents.nodes.translation_engine_node as engine_node

    monkeypatch.setattr(settings, "enable_live_llm_inference", False, raising=False)
    if not settings.openai_api_key:
        monkeypatch.setattr(settings, "openai_api_key", "sk-test-not-a-real-key", raising=False)

    # The translation engine is a process singleton whose `self.llm` is bound
    # once at construction, so a stale binding (and an exhausted fake-model
    # iterator) otherwise survives across tests. Reset it so each test builds a
    # fresh engine against the current LLM mode.
    engine_node._engine = None
    llm_module.reset_llm_cache_for_test()
    try:
        yield
    finally:
        engine_node._engine = None
        llm_module.reset_llm_cache_for_test()


@pytest.fixture
def fresh_engine_for_db(tmp_path, monkeypatch):
    """Yield app.core.database with engine + SessionLocal swapped to a tmp SQLite DB.

    Use this in any test fixture that previously did:

        importlib.reload(app.core.database)
        core_db.init_db()

    The reload pattern poisons FastAPI dependency overrides in other test
    modules; the in-place swap preserves function identity.
    """
    import app.core.database as core_db

    db_path = tmp_path / "test_fresh.db"
    new_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", new_url)

    saved_engine = core_db.engine
    saved_session_local = core_db.SessionLocal
    saved_url = core_db.DATABASE_URL

    core_db.DATABASE_URL = new_url
    core_db.engine = create_engine(
        new_url,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    core_db.SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=core_db.engine
    )

    core_db.init_db()

    try:
        yield core_db
    finally:
        try:
            core_db.engine.dispose()
        finally:
            core_db.engine = saved_engine
            core_db.SessionLocal = saved_session_local
            core_db.DATABASE_URL = saved_url
