# TMX-MQM-6 — ensemble aggregation + conservation constraint (pure)

**State**: `[Done]` · **Owner**: Agent & AI · **Sprint**: MQM Keystone (Phase 1)
**Reversibility**: `two-way` (pure, additive helpers). **Pre-mortem**: conservation heuristic could false-accept a coincidental match (documented). **Blast radius**: new `app/services/mqm_review.py` only (not yet wired into the live reviser — that lands with the revise loop).

**Gates**: G1 ✓ (the two backstops for *no vacuous green* + *conservation before correctness*; pure + tested) · G2 N/A · G3 ✓ (ensemble takes most-severe + escalates on disagreement; conservation rejects out-of-scope edits).

## 1–3. Task / Spec / Design
Two pure primitives for the critique loop. **Ensemble (§6.4):** merge N judges' annotations per span taking the MOST SEVERE (never averaged) and ESCALATE on disagreement (a span not all judges flagged, or differing severities). **Conservation (§6.3):** reject a revision that altered any non-flagged chunk of the original. AC-1 most-severe wins; AC-2 disagreement → escalate, agreement → no; AC-3 in-scope edit accepted, out-of-scope rejected. Out of scope: wiring into the live reviser/ensemble runner (lands with the revise loop after the cutover).

## 4. Code
`app/services/mqm_review.py` — `aggregate_ensemble` + `EnsembleResult`; `enforce_conservation` + `ConservationResult` + `_unflagged_chunks`.

## 5. Test
`pytest tests/test_mqm_review.py -q` → 6 tests (most-severe, agreement/disagreement, missing-span escalation, conservation accept/reject).

## 6–7. Red team / Fix
Risk: conservation substring heuristic false-accepts → acceptable for the backstop; a stricter alignment is a future refinement. Risk: span-key collisions across judges → keyed by segment+dimension+target-text. No findings.

## 8. Deploy
- [x] Commit: `875751c` (batched: "TMX-MQM-4/6/5a-emit: independent judge (shadow) + ensemble/conservation + audit emit") · Pushed: **gated on Kapil** · [x] active_tasks updated

## Status log
| 2026-06-15 | — | `[Done, pending push]` | pure helpers ready; wired with the revise loop |
