# TMX-SSOT-TIER (steps 1–3) — fix the metadata funnel + tier→profile refinement + unify the governance rule

**State**: `[WIP]`
**Owner**: Quality & Regulatory
**Sprint**: MQM Keystone / Phase 0 (stop the vacuous green)
**Started**: 2026-06-15
**Closed**: —
**Reversibility**: `two-way` (a new read method + a data-driven override map + a predicate extraction; revertable. The one-way step 4 — removing the dead `MqmAnnotation.risk_tier` int — is DEFERRED to Kapil sign-off.)
**Pre-mortem**: if this fails in production, the failure mode is *the funnel fix changes a LIVE verdict via the source-language node*. The red team caught this: defining `get_document_metadata` (previously undefined → AttributeError → always `'en'`) re-activates the source-language node, which feeds the live `constraint_pack`/gate. Resolved by surfacing the DECLARED `Document.source_language` column so the node is DETERMINISTIC: en-source docs (the pilot) resolve to `'en'` exactly as before; a declared non-en source is now honoured instead of the latent always-`'en'` (a correctness fix, NOT a speculative behaviour, and never fragile auto-detection). The verdict authority `evaluate_verdict` reads neither `content_metadata` nor the profile; `content_metadata` feeds ONLY the MQM shadow; the metric profile is resolved ONLY on the shadow path. So no shadow-→-live leak beyond the deterministic declared source language.
**Blast radius**: `app/services/db_service.py` (+1 read method — graph already calls it), `app/core/metric_profiles/resolution.py`, `app/core/profile_enums.py`, `app/schemas/api_v1.py` (validator body only — request shape + error message unchanged), `app/core/profile_resolver.py`. No live verdict.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — (a) needed: `get_document_metadata` is CALLED by the graph but undefined → AttributeError swallowed → `content_metadata` always `{}` → the MQM shadow always scores the default profile (a dead funnel); (b) <5 callers; (c) backend; (d) reuses the existing `_ARCHETYPE_TO_PROFILE` seam + the `get_session` pattern + `MetricProfile` as the SSOT — no new registry; (e) ships with tests.
- [x] **G2 Reproduce-the-failure** — a Document whose `meta_json` carries `{archetype,tier}` yielded `content_metadata={}` (default profile); `test_funnel_now_selects_refined_profile` reproduces it and proves the funnel now populates and selects the refined profile.
- [x] **G3 Completion** — `get_document_metadata` returns the profile + declared source language; the funnel populates; tier refines the canonical profile; the governance rule lives in one predicate; no live verdict beyond the deterministic declared source language.

---

## 1. Task

The vision wants risk-tier-driven rigor, but the tier vocabularies are dead: `ContentRiskTier` (A/B/C) dead-ends in `JobProfile.tier`; `MqmAnnotation.risk_tier:int` is never assigned; the engine reads neither. Worse, the metric-profile funnel that WOULD carry archetype/tier is itself dead — `get_db_service().get_document_metadata(...)` (graph.py:109,135) is undefined, so the `AttributeError` is swallowed and `content_metadata` is ALWAYS `{}`. Collapse this onto the canonical SSOT (`MetricProfile`): (1) fix the funnel so archetype/tier reach resolution; (2) make `ContentRiskTier` DERIVE a profile via `resolution.py` (never a 3rd registry); (3) unify the duplicated `INFORMATIONAL!=TIER_A` rule into one predicate. Addenda: A2 (rigor lives in the metric profile the engine scores), A3 (no fabricated metadata — `{}` falls through honestly), Tier-0 SSOT (one tier signal, one governance predicate).

## 2. Spec — acceptance criteria

- [ ] AC-1 (corrected after red team): `DatabaseService.get_document_metadata(doc_id)` returns the Document's `meta_json` PLUS the declared `source_language` column (`{}` only for an unknown doc — A3). Surfacing `source_language` makes the (previously-dead, always-`'en'`) source-language node DETERMINISTIC on the declared column: en-source docs resolve to `'en'` (unchanged); a declared non-en source is honoured (corrects a latent always-`'en'` bug; NOT byte-identical for those docs, but deterministic — not auto-detection).
- [ ] AC-2 (reproduce-the-failure): a Document with `meta_json={archetype, tier}` now yields a non-empty `content_metadata` reaching `resolve_metric_profile` and selecting the expected profile (was always `smpc_pil` by the swallowed AttributeError).
- [ ] AC-3: `resolve_profile_id` consults a data-driven `_ARCHETYPE_TIER_TO_PROFILE` override INSIDE the archetype branch (after content-type, before the plain-archetype fallback). Tier only REFINES an archetype already present — it never selects alone. Every unmapped `(archetype,tier)` yields exactly today's profile (all 11 existing resolution tests stay green).
- [ ] AC-4: The `INFORMATIONAL!=TIER_A` invariant lives in ONE predicate (`profile_enums.is_tier_archetype_compatible`), called by both `api_v1` (live) and `profile_resolver` (legacy). The `api_v1` request shape AND its `ValueError` message are unchanged (`test_api_contracts.py` stays green).
- [ ] AC-5: No live verdict moves — the engine is shadow (`mqm_engine_enabled=False`); only the shadow's profile resolution changes.

Out of scope (DEFERRED): **step 4 (one-way, Kapil sign-off)** — remove the dead `MqmAnnotation.risk_tier:int` (`mqm_annotation.py:71`, zero refs) + fix the `mqm_engine.py:17-21` docstring that falsely claims a 'risk-tier' owns insufficient-sample routing. Treated one-way (field removal on the shared §5.7 currency). Also out: soft-removing the fully-dead `profile_resolver.py`; per-segment content-type detection (TMX-MQM-5c-deepen).

## 3. Design

Canonical SSOT = `MetricProfile` (the only signal the engine scores against). Tier collapses by FUNNELLING into it via `resolution.py`, not a new registry. The funnel fix is one added read method — graph.py already calls it. Verified shadow-safe (see pre-mortem). The tier override is a dict (config-not-branching): `TIER_A` ("zero tolerance") escalates an archetype to the strictest profile (`smpc_pil`); listed only where it sharpens beyond the archetype default. The governance rule is extracted to one predicate; each call site keeps its own message so the live API contract is untouched.

Alternatives rejected: (a) a new tier registry/enum — Tier-0 SSOT violation; (b) tier selecting a profile alone — tier is a refinement of an archetype, not a standalone signal; (c) returning `source_language` from `get_document_metadata` — would change the live language-pack choice; kept out so the fix is shadow-only; (d) removing the dead int / fixing the engine docstring now — one-way on the shared currency, deferred to Kapil with step 4.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/services/db_service.py` | +~14 | `get_document_metadata(doc_id) -> dict` (the missing funnel method) |
| `app/core/metric_profiles/resolution.py` | +~12 | `_ARCHETYPE_TIER_TO_PROFILE` + consult it in the archetype branch |
| `app/core/profile_enums.py` | +~6 | `is_tier_archetype_compatible(archetype, tier)` predicate |
| `app/schemas/api_v1.py` | ~22 | validator calls the predicate (message + shape identical) |
| `app/core/profile_resolver.py` | ~61 | resolver calls the predicate (message kept) |
| `tests/test_ssot_tier.py` | new | funnel returns meta / `{}`; reproduce-the-failure; tier refinement; predicate |

## 5. Eval / Test

```
python -m pytest tests/test_ssot_tier.py tests/test_metric_profile_resolution.py tests/test_profile_resolver.py tests/test_api_contracts.py -q
```
```
all pass — funnel returns meta+declared source_language; en→'en'/de→'de';
reproduce-the-failure (OPERATIONAL+TIER_A → smpc_pil through the real funnel);
tier refinement default-preserving (11 existing cases green); enum-member
resolution; predicate blocks INFORMATIONAL+TIER_A with the identical api message.
Full regression 230 passed.
```

## 6. Red team

4-lens adversarial review (workflow `wctx81sw8`). The shadow-safety claims for `content_metadata`/tier/predicate were ALL verified sound (content_metadata is shadow-only; tier refinement has no live caller; the predicate is byte-equivalent). **But two real defects:** (1) [high] defining `get_document_metadata` re-activates the previously-dead LIVE source-language node — before it RAISED → `except` → always `'en'`; after it returns a dict → the node runs `detect_language`, feeding the live `constraint_pack`/gate. My "byte-identical source-language" claim was wrong. (2) [low] `resolve_profile_id` keyed on `str(arch).upper()` mis-handles enum MEMBERS (`'ClassName.MEMBER'`), silently falling to the default profile (masked because JSON round-trips to strings).

## 7. Fix

(1) `get_document_metadata` now surfaces the DECLARED `Document.source_language` so the source-language node is deterministic on the column — en unchanged, declared non-en corrected (no auto-detection); AC-1 + pre-mortem reframed honestly (NOT byte-identical for non-en); added a test pinning en→'en'/de→'de'. (2) `resolve_profile_id` normalises via `_norm` (`x.value` for enum members) + a test proving member-keyed == string-keyed resolution. Also added a one-line note at the dead `MqmAnnotation.risk_tier` pointing to step 4. Re-ran: all green.

## 8. Deploy

- [ ] Commit: <SHA after commit>
- [ ] Pushed to origin (branch `feat/mqm-keystone`, PR #14)
- [ ] `.context/active_tasks.md` + `MQM-DELIVERY-BACKLOG.md` updated

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-15T00:00Z | — | `[WIP]` | Created (batch 3); steps 1–3 (funnel + tier refinement + rule unify); step 4 (dead-field removal) deferred to Kapil (one-way) |
