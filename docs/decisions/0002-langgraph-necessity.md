# ADR-0002: Keep LangGraph for the pilot; revisit at v3.5

**Date:** 2026-05-13
**Status:** accepted

## Context

The TransMax pipeline (`app/agents/graph.py`) orchestrates the
translation flow through LangGraph: 8 nodes, 1 conditional edge
(`run_quality_gates` → `refine` | `reflexion`), 1 cycle
(`refine` → `gates`), and a `TypedDict` state object.

Concrete surface as of this ADR:

```
validate → load_segments → constraints → translate → gates
                                                       ├─ refine → gates  (loop)
                                                       ├─ reflexion → finalize → END
```

LangGraph features we use:
- `StateGraph` for declarative wiring
- `add_conditional_edges` for the gates branch
- `add_edge` for the cycle

LangGraph features we do NOT use:
- Checkpointing / persistence
- Streaming
- Human-in-the-loop interrupts
- Sub-graphs / composition
- Tool calling integration

We also import `langchain_core.messages` (`SystemMessage`, `HumanMessage`)
and `langchain_openai.ChatOpenAI` in nodes — but the actual LLM call
flows through `app.services.llm.get_llm`, which already abstracts the
provider. The LangChain wrappers are mostly dead weight in this codebase.

A red-team prompt as part of Sprint 2 review asked whether a more
optimised agentic implementation is possible and whether LangGraph is
required. This ADR captures the answer.

## Decision

Keep LangGraph for the pilot. The orchestration value is marginal but
real (≈80 LOC of equivalent control flow + the conditional + the
cycle), and replacing it mid-pilot disturbs the eval harness, the
`@traced` decorator wiring, and ~30 tests that exercise the compiled
graph. The downside (one extra dependency, version risk, and
`langchain_core` / `langchain_openai` weight we don't need) is bounded
and tracked.

Plan a **swap-out worksheet TMX-3500-ARCH-LANGGRAPH-REVIEW** for v3.5
that replaces the graph with a plain async `Pipeline` class — 8 node
functions, a `dispatch(state)` method with a `while iteration_count <
MAX` loop, and the conditional as a 3-line `if/elif/else`. The
TypedDict state stays unchanged. Net delta projected at –200 LOC and
fewer imports.

Independently of the LangGraph decision, **drop the unused
`langchain_core` and `langchain_openai` imports** where they are
single-line aliases for things `app.services.llm` already does
natively. This is bookkeeping, not architecture, and is in scope for
the v3.5 worksheet.

## Consequences

**What gets better (with this decision):**
- Pilot ships on time. The audit ledger v2 (TMX-3101 / TMX-3104 /
  TMX-3110) is the load-bearing differentiator; arch churn would
  starve it.
- The eval harness (`tests/evals/`) keeps its current shape.
- New contributors recognise the LangGraph idiom from prior art.

**What gets worse:**
- One extra dependency to track for CVEs / version drift. Mitigation:
  Dependabot already pins LangGraph / LangChain in
  `.github/dependabot.yml`.
- LangChain wrapper objects (`ChatOpenAI`, `SystemMessage`) duplicate
  what `app.services.llm` already does. Mitigation: TMX-3500-ARCH
  cleanup includes removing these single-line aliases.
- `@traced` wraps each node manually — a Pipeline class would centralise
  this. Accepted cost for the pilot.

**What becomes possible:**
- Future swap to a plain Pipeline class is straightforward because the
  state is a `TypedDict` (no LangGraph-specific persistence to migrate)
  and nodes are already plain async functions.

**What becomes hard:**
- Adding a second flow (e.g. a re-translation-only or an audit-only
  pipeline) tempts new LangGraph nodes when a Pipeline class would
  compose better. Watch for this in PR review.

## Alternatives considered

- **Replace LangGraph with a plain async `Pipeline` class now.** The
  pipeline is small enough that this would work (~80 LOC of swap),
  but it pulls churn into Sprint 2 when the audit chain is the critical
  path. Rejected for v3.0; **accepted for v3.5** via the planned
  TMX-3500-ARCH-LANGGRAPH-REVIEW worksheet.

- **Keep LangGraph, drop LangChain.** LangGraph is the orchestrator;
  LangChain is the message / model wrappers. We could keep the former
  and remove `langchain_core` + `langchain_openai` since `app.services.llm`
  already abstracts the provider. Viable; **rolled into TMX-3500-ARCH**
  as a sub-task to share the diff. Not worth a separate loop.

- **Move to a managed agent SDK (e.g. Anthropic's Managed Agents).**
  Decoupled from our orchestration and pricing model; adds a new
  external dependency at the pilot's worst possible time. Rejected.

- **Hand-roll the conditional + cycle inline in `run_pipeline_background`.**
  Cheapest option (~30 LOC). Rejected because the eval harness and
  tracing rely on the graph compilation step as the test boundary,
  and the maintenance cost of replicating that boundary by hand isn't
  worth saving 50 LOC.

## Affected teams / surfaces

- **Agent & AI pod** (graph owner) — owns the v3.5 swap worksheet.
- **Platform & Observability pod** — `@traced` decorator behaviour must
  survive the swap.
- **Quality & Regulatory pod** — eval harness (`tests/evals/`) tests
  exercise the compiled graph and must keep passing.

Affected paths:
- `app/agents/graph.py` — current graph compilation.
- `app/agents/nodes/*.py` — translation + reverse-translate nodes.
- `tests/evals/` — eval runner imports the compiled graph.
- `tests/test_tmx_3110_double_write.py` and any future double-write tests.
- `app/services/llm.py` — already abstracts the provider; survives unchanged.

## Spawned worksheets

- **TMX-3500-ARCH-LANGGRAPH-REVIEW** (v3.5, deferred) — swap LangGraph
  for a plain `Pipeline` class; drop `langchain_core` / `langchain_openai`
  imports; remove `@traced` per-node wrapping in favour of pipeline-level
  instrumentation.
