"""
TMX-3012c — pipeline runner carries tenant context.

`run_pipeline_background` spawns a fresh asyncio event loop via
`asyncio.run(...)`. Once the explicit `organization_id=DEFAULT_ORG_ID`
literals are removed from the service layer, every DB write inside the
pipeline (audit records, scorecards, DLQ entries, segments) relies on the
auto-inject mixin reading from `current_org_id()`. The runner MUST therefore
enter `org_context(org_id)` before invoking the LangGraph pipeline.

This test asserts:
  - run_pipeline_wrapper sees the passed org_id via current_org_id()
  - org_context is restored cleanly after the wrapper exits
  - omitting org_id is a TypeError (kwarg-only and required)
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_run_pipeline_wrapper_enters_org_context(monkeypatch):
    """The wrapper sets `current_org_id()` to the passed `org_id` for the
    duration of the graph invocation, and restores it on exit."""
    from app.core.tenant_context import current_org_id

    captured = {}

    async def fake_ainvoke(state):
        captured["org_at_invoke"] = current_org_id()
        return {"error": None}

    # Patch the graph_app.ainvoke to capture context inside the wrapper.
    from app.agents import runner
    monkeypatch.setattr(runner.graph_app, "ainvoke", fake_ainvoke)

    target_org = "11111111-1111-1111-1111-111111111111"

    # Ensure no leakage from the outer test.
    assert current_org_id() is None

    await runner.run_pipeline_wrapper(
        doc_id="test-doc-1",
        target_lang="es",
        org_id=target_org,
    )

    assert captured["org_at_invoke"] == target_org
    # Context restored after exit.
    assert current_org_id() is None


def test_run_pipeline_background_propagates_org_id(monkeypatch):
    """The sync entry-point passes `org_id` through to the wrapper."""
    from app.core.tenant_context import current_org_id

    seen = {}

    async def fake_wrapper(doc_id, target_lang, segment_ids=None, *, org_id):
        seen["doc_id"] = doc_id
        seen["target_lang"] = target_lang
        seen["org_id"] = org_id
        seen["org_via_contextvar"] = current_org_id()

    from app.agents import runner

    # We patch run_pipeline_wrapper to assert what the sync entrypoint passed.
    # The sync entrypoint enters org_context(org_id) BEFORE awaiting the
    # wrapper inside asyncio.run, so current_org_id() is set when fake_wrapper
    # runs only IF the wrapper enters the context. Since we patched the
    # wrapper itself, we need to manually re-enter to mirror prod behavior.
    # Simpler: assert the kwarg arrived intact, which proves propagation.
    monkeypatch.setattr(runner, "run_pipeline_wrapper", fake_wrapper)

    runner.run_pipeline_background(
        "doc-2",
        "fr",
        org_id="22222222-2222-2222-2222-222222222222",
    )

    assert seen["doc_id"] == "doc-2"
    assert seen["target_lang"] == "fr"
    assert seen["org_id"] == "22222222-2222-2222-2222-222222222222"


def test_run_pipeline_background_requires_org_id_kwarg():
    """A missing `org_id` is a TypeError (kwarg-only, required, no default)."""
    from app.agents import runner

    # Deliberately omit org_id; passing via **{} keeps mypy quiet at the
    # call site so we don't add a suppression comment here.
    bad_call_kwargs: dict = {}
    with pytest.raises(TypeError):
        runner.run_pipeline_background("doc-3", "de", **bad_call_kwargs)
