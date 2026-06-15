# TMX-DASH-JUDGE-LABEL — honest dashboard agent labels

**State**: `[Done, pending push]` · **Owner**: Reviewer Frontend / Platform · **Sprint**: Phase 0 (honesty)
**Reversibility**: `two-way`. **Pre-mortem**: none (label-only). **Blast radius**: `app/api/dashboard.py` `_EVENT_TYPE_TO_AGENT` names.

**Gates**: G1 ✓ (closes the A2 cosmetic-mislabel hazard; minimal) · G2 ✓ (audit found GATE_* events presented as "Reviewer agent") · G3 ✓ (the deterministic gate is now labelled honestly).

## 1–3. Task / Spec / Design
The audit (A2) found the dashboard maps deterministic GATE_* events to "Reviewer agent" — dressing the deterministic gate as an independent assessor in a regulator-facing view, when no independent judge is in the live verdict path yet. Rename the visible NAMES honestly (GATE_* → "Quality gate (deterministic)", REVERSE_TRANSLATE → "Back-translation check"), keeping the lane `id`s stable so the activity/agent-activity structure + its tests are unchanged. "Judge" is reserved for the real judge (emits MQM_JUDGE_SHADOW to v2 today). AC-1 GATE_* no longer reads "Reviewer agent". Out of scope: surfacing v2 judge events in the v1-based feed (when the feed reads v2).

## 4. Code
`app/api/dashboard.py` — `_EVENT_TYPE_TO_AGENT` names (ids + actor_type unchanged).

## 5. Test
`pytest tests/test_dashboard_activity_feed.py -q` green (canonical lane ids unchanged); names verified honest.

## 6–7. Red team / Fix
Risk: breaking the canonical-four lane test → averted by keeping ids stable (only names changed). No findings.

## 8. Deploy
- [ ] Commit: <this commit; SHA backfill> · Pushed: **gated on Kapil** · [x] active_tasks updated

## Status log
| 2026-06-15 | — | `[Done, pending push]` | deterministic gate no longer mislabelled as an agent |
