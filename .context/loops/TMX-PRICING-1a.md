# TMX-PRICING-1a — Register the configured default model in the pricing registry

**State**: `[Done]` — `7b9daeb` on origin/main  ·  **Owner**: Platform  ·  **Sprint**: 2  ·  **Started/Closed**: 2026-06-03
**Reversibility**: `two-way` — one additive dict entry. Revert by removing it.
**Pre-mortem**: if wrong, the recorded cost for the default model would be inaccurate — mitigated by using the *confirmed public* GPT-4 Turbo rate ($10/$30 per 1M), not a guess (A3).
**Blast radius**: `app/core/model_pricing.py` only (data). No code-path change.

**Gates**: G1 — closes a latent `UnknownModelError` on `cost_for(settings.default_gpt_model)` (robustness + trust: accurate regulator-facing cost). G2 — red test reproduces the gap first. G3 — `cost_for(default_gpt_model)` returns a sane cost.

## 1. Task
`settings.default_gpt_model = "gpt-4-turbo-preview"` is the model-of-record in the audit snapshot (graph.py:114) + A6-2 usage (translation_engine.py:369), but was absent from the canonical registry, so `cost_for(default_gpt_model)` raised `UnknownModelError`. Register it at its confirmed public rate. Addenda: A3 (only confirmed rates; loud on unknowns), A6 (accurate supplier cost).

## 2. Spec
- [x] AC-1: `get_pricing(settings.default_gpt_model)` returns valid pricing (no raise).
- [x] AC-2: `gpt-4-turbo-preview` = $10/1M in, $30/1M out (confirmed public rate).
- [x] AC-3: `cost_for(default_gpt_model, 1M, 1M) == 40.00`.
- [x] AC-4: `cached_input_per_1m <= input_per_1m` (A3 — never under-bill).

Out of scope: gpt-4.1 / Claude / embedding tiers — deferred until confirmed 2026 rates (A3: never guess). Changing which tier A6-2/documents *cost at* (they deliberately use gpt-4o-mini per Feature-5) — unchanged.

## 3. Design
Add `gpt-4-turbo-preview: ModelPricing(10.00, 30.00, cached=10.00)`. gpt-4-turbo has no published cached-input discount (a gpt-4o-era feature), so cached == input — conservative, never under-bills.

## 4. Code
| File | Change |
|---|---|
| `app/core/model_pricing.py` | +`gpt-4-turbo-preview` entry + rationale comment |
| `tests/test_pricing_default_model.py` | new — 3 tests (red-before-green) |

## 5. Test
`pytest tests/test_pricing_default_model.py` → 3 passed (was 3 red). Adjacent usage+budget 13/13. Ratchet 17/17. Full suite — stage 8.

## 6. Red team
Rate accuracy is the only risk; used the well-established public GPT-4 Turbo rate, not a guess. Cached==input is conservative. Other model tiers explicitly deferred (loud UnknownModelError remains correct for them).

## 7. Fix
None — clean.

## 8. Deploy
- [x] Ruff clean · Ratchet 17/17
- [ ] Commit / push (after full suite)

### Spawned
- **TMX-PRICING-1a-rates** — register gpt-4.1 / Claude (Opus/Sonnet/Haiku) / embedding tiers once confirmed 2026 per-1M rates are sourced.

## Status log
| When | From | To | Note |
|---|---|---|---|
| 2026-06-03T~21:40Z | — | `[Verify]` | Entry + 3 tests; adjacent green; awaiting full suite |