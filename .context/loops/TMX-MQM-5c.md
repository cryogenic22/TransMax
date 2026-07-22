# TMX-MQM-5c — content-type → metric-profile resolution

**State**: `[Done]` · **Owner**: Quality & Regulatory · **Sprint**: MQM Keystone (Phase 1)
**Reversibility**: `two-way` (additive). **Pre-mortem**: wrong profile → wrong shadow score (shadow only; no live verdict). **Blast radius**: new `resolution.py`; `mqm_shadow.resolve_metric_profile` delegates; `graph.validate_request` stashes `content_metadata`.

**Gates**: G1 ✓ (reconciles the two legacy profile systems onto the registry, replaces the default-only seam, ships tests) · G2 N/A · G3 ✓ (the shadow now scores against the content-appropriate profile).

## 1–3. Task / Spec / Design
Replace the single-default-profile seam with a real map from document content-type (or legacy archetype) → metric profile, reconciling `regulatory_profiles`/`profile_resolver` onto the registry. Pure, never-raises (falls back to default). AC-1 content_type/doc_type → profile; AC-2 archetype fallback; AC-3 explicit override wins; AC-4 unknown id → default. Out of scope: full per-segment content-type detection.

## 4. Code
`app/core/metric_profiles/resolution.py` (new); `app/agents/nodes/mqm_shadow.py` (delegate + drop unused import); `app/agents/graph.py` (`validate_request` stashes `content_metadata`).

## 5. Test
`pytest tests/test_metric_profile_resolution.py -q` → 10 mappings + override/fallback green. Shadow tests still green.

## 6–7. Red team / Fix
Risk: metadata absent → default (documented, safe). Risk: bad profile id → fallback to default (tested). No findings.

## 8. Deploy
- [x] Commit: `737993c` (batched: "TMX-MQM-5c/BB-STRICT/AUTH-AUDIT: profile resolution + enforce strict rules + audit access") · Pushed: **gated on Kapil** (`feat/mqm-keystone`) · [x] active_tasks updated

## Status log
| 2026-06-15 | — | `[Done, pending push]` | content→profile resolution live (shadow) |
