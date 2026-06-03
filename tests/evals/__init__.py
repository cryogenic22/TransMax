"""TransMax AI eval harness — golden cases that exercise the deterministic
quality gates against canonical and tampered translations.

The harness is *deliberately offline*: it does not call an LLM. Eval cases
are structured `(source, target, expected_defects)` triples that test
whether the deterministic gates catch what they should, and only what they
should, on known inputs.

Live LLM-driven golden runs (Track 3 in `TRANSMAX_HEADLESS_AGENT_SPEC.md`)
gate on `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` and live in `tests/evals/live/`
(deferred until v3.0 epic E7.9 lands).

See `tests/evals/README.md` for the full design and how to add a case.
"""
