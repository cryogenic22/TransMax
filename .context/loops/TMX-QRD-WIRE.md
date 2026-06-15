# TMX-QRD-WIRE — fire the dead-but-tested QRD date/header checks (flag-gated, exercisable)

**State**: `[Done]`
**Owner**: Quality & Regulatory
**Sprint**: MQM Keystone / Phase 4 (compliance)
**Started**: 2026-06-15
**Closed**: 2026-06-15
**Reversibility**: `two-way` (new default-OFF flag + a pure resolver + an OPTIONAL backwards-compatible API field + a flag-gated graph wire; revertable)
**Pre-mortem**: if this fails in production, the failure mode is *the QRD checks flip a verdict unexpectedly* — guarded by a default-OFF flag (`enable_qrd_checks`); with it off, `regulatory_profile_for_gate` returns `None`, so `check_segment` runs ZERO QRD checks → byte-identical. The verdict delta when ON is documented (header→REVIEW_REQUIRED, date→band drop), so a deployment opts in knowingly. NB: `enable_qrd_checks` is a GLOBAL (process-wide) rollout flag, same posture as `mqm_engine_enabled` — true per-tenant keying is a follow-up, not claimed here.
**Blast radius**: `app/core/config.py` (1 flag), `app/core/regulatory_profiles.py` (1 pure helper), `app/schemas/api_v1.py` (1 optional field), `app/agents/graph.py` (import + 1 content_metadata key + the gate's `check_segment` call). No `quality_gate.py` change (the checks already exist + are tested).

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — (a) needed: `check_date_formatting`/`check_mandatory_headers` + the `regulatory_profiles` registry are FULLY IMPLEMENTED + unit-tested but DEAD — `check_segment` gates them behind `if profile_id:` and EVERY caller passes `profile_id=None` (a vacuous-green seam: a regulatory gate that never runs); (b) <5 callers; (c) backend; (d) reuses the existing checks + `get_profile` + the now-live metadata funnel (TMX-SSOT-TIER) — NO new check logic, NO new registry; (e) ships with tests + is EXERCISABLE (the optional `regulatory_profile` field lets a job opt a profile in end-to-end).
- [x] **G2 Reproduce-the-failure** — the dead seam is reproduced: `test_qrd_checks_dead_when_flag_off` (tagged job, flag off → no QRD) + `test_qrd_date_check_fires_with_resolved_profile` (flag on → bad date fires).
- [x] **G3 Completion** — a job tagged with a known `regulatory_profile` makes the QRD checks fire in the live gate when `enable_qrd_checks` is on; byte-identical when off (red team traced + ran the full funnel).

---

## 1. Task

The QRD authority checks (date-format + mandatory-headers per `regulatory_profiles.py`: EMA/MHRA/FDA/SFDA/PMDA) are implemented and tested (`test_profile_gates.py`) but never run: `quality_gate.check_segment` calls them only `if profile_id:`, and every production caller passes `None` — `profile_id` was added to the signature but never threaded. Wire it: a job can be tagged with a `regulatory_profile`, which (via the now-live metadata funnel from TMX-SSOT-TIER) reaches the gate, and the checks fire — **only** when the new default-OFF `enable_qrd_checks` flag is on. Addenda: A2 (deterministic regulatory gate), A3 (unknown profile → no check, never a default), A7-adjacent backwards-compatible API addition.

## 2. Spec — acceptance criteria

- [ ] AC-1: New `enable_qrd_checks: bool = False`. With it off, `regulatory_profile_for_gate(...)` returns `None` and the live gate's violations/verdict are byte-identical to today (the QRD block never runs).
- [ ] AC-2: `regulatory_profile_for_gate(content_metadata, *, enabled)` is pure: returns the explicit `regulatory_profile` tag ONLY when `enabled` AND it is a KNOWN profile (`get_profile` non-None); `None` for disabled / absent / unknown (A3 — never a fabricated default).
- [ ] AC-3: `JobProfileRequest` gains an OPTIONAL `regulatory_profile: Optional[str] = None` (backwards-compatible — existing requests still validate); it flows via `model_dump()` → `meta_json` → `content_metadata` → the gate.
- [ ] AC-4: When `enable_qrd_checks` is on and a job carries a known `regulatory_profile`, the live gate (`run_quality_gates`) passes that `profile_id` to `check_segment`, so `check_date_formatting`/`check_mandatory_headers` fire.
- [ ] AC-5: The worksheet documents the verdict delta the flag introduces (header STRUCTURE_ERROR=MAJOR→REVIEW_REQUIRED; date FORMATTING_ERROR=MINOR→band drop) AND the header-regex EN-only limitation (non-EN profiles' header check no-ops — no multilingual QRD claim).
- [ ] AC-6: `test_profile_gates.py` (which calls `check_segment` with an explicit `profile_id`) stays green — the gate contract is unchanged; the flag is enforced at the graph wire, not inside `check_segment`.

Out of scope: auto-resolving the profile from authority/locale/doc_type (needs upload to capture those — a follow-up **TMX-QRD-CAPTURE**); pinning QRD defects to MINOR/warn-only (a documented one-line follow-up if the pilot finds MAJOR too aggressive); the EN-only header regex (**TMX-QRD-MULTILINGUAL**); true per-tenant keying of `enable_qrd_checks` (**TMX-QRD-PER-TENANT**, shared with `mqm_engine_enabled`).

## 3. Design

Graph-only flag gate (NOT an engine-level guard): the flag is applied where the live verdict path threads `profile_id` into `check_segment` (the gate node). This keeps `check_segment`'s contract intact (so `test_profile_gates.py` stays green) — the QRD checks are still activated by a `profile_id`, and the ONLY live caller that supplies one is the flag-gated gate wire. One pure helper `regulatory_profile_for_gate(content_metadata, *, enabled)` encapsulates both the flag gate AND the A3 validation, so the safety property (off ⇒ None ⇒ byte-identical) is unit-tested without running the graph node. Natural severities kept (a regulatory gate SHOULD review structural defects); the global flag is the deployment opt-in (per-tenant keying deferred).

Alternatives rejected: (a) engine-level guard in `check_segment` (`if profile_id and enable_qrd_checks`) — changes the gate contract + breaks `test_profile_gates.py`; the graph is the only live caller threading `profile_id`, so the graph gate is sufficient; (b) auto-resolve authority/locale — `regulatory_profiles.resolve_profile` needs an `authority` the metadata doesn't capture; guessing it violates A3; (c) shipping the wire WITHOUT the optional API field — inert (no job can resolve a profile), borderline-vacuous (fails G1); the field makes it exercisable end-to-end.

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/core/config.py` | ~+6 | `enable_qrd_checks: bool = False` |
| `app/core/regulatory_profiles.py` | +~10 | `regulatory_profile_for_gate(content_metadata, *, enabled)` |
| `app/schemas/api_v1.py` | +~4 | `JobProfileRequest.regulatory_profile: Optional[str] = None` |
| `app/agents/graph.py` | +~5 | import `get_settings`; add `regulatory_profile` to the content_metadata keys; gate passes the resolved `profile_id` |
| `tests/test_qrd_wire.py` | new | flag gate (off→None byte-identical / on→resolves); A3 unknown→None; check fires on / dead off; API field backwards-compatible |

## 5. Eval / Test

```
python -m pytest tests/test_qrd_wire.py tests/test_profile_gates.py tests/test_api_contracts.py -q
```
```
all pass — flag off → None (byte-identical) / on+known → resolves; A3 unknown &
non-str → None; QRD date check fires on / dead off; JobProfileRequest field
optional + flows. test_profile_gates (gate contract) + api_contracts unchanged.
Full regression 234 passed.
```

## 6. Red team

3-lens adversarial review (workflow `w2x2a4wv4`). Two lenses verdict **ship** with zero defects — they traced the full funnel + ran the tests and confirmed: flag-off is genuinely byte-identical (the engine's internal `check_segment` and all other callers pass no `profile_id`; only the flag-gated graph gate does); the optional field is backwards-compatible; the checks fire end-to-end when on; the MINOR/MAJOR severities + the EN-only header regex are honestly disclosed. **One real (low) defect:** the worksheet/config called `enable_qrd_checks` "per-tenant" when it's a GLOBAL process-wide flag (same loose convention as `mqm_engine_enabled`). Plus a cheap hardening: a non-str `regulatory_profile` blob would `TypeError` in `get_profile`.

## 7. Fix

(1) Reframed the flag as a GLOBAL (process-wide) rollout flag in the config comment + pre-mortem + design (per-tenant keying = a noted follow-up, same posture as `mqm_engine_enabled`); the verdict delta itself was already disclosed. (2) `regulatory_profile_for_gate` now guards `isinstance(pid, str)` → a malformed metadata blob no-ops (A3) instead of routing to the gate's BLOCKED fail-safe; added a non-str-tag test. Re-ran: green.

## 8. Deploy

- [x] Commit: `7e3fa1c`
- [x] Pushed to origin (branch `feat/mqm-keystone`, PR #14)
- [x] `.context/active_tasks.md` + `MQM-DELIVERY-BACKLOG.md` updated

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-15T00:00Z | — | `[WIP]` | Created (batch 4); unblocked by the TMX-SSOT-TIER funnel fix; flag-gated + exercisable via the optional regulatory_profile field |
| 2026-06-15T00:00Z | `[WIP]` | `[Done]` | Shipped in `7e3fa1c`; red team verified byte-identical-off + end-to-end fire; fixed per-tenant overclaim + non-str hardening |
