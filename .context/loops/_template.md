# TMX-XXXX — <Title>

**State**: `[Spec]`
**Owner**: <pod>
**Sprint**: <n>
**Started**: YYYY-MM-DD
**Closed**: —
**Reversibility**: `two-way` <!-- or `one-way` (schema migrations, public-API shape changes, destructive ops) → human approval before stage 4 -->
**Pre-mortem**: <1 line — "if this fails in production, the failure mode is …">
**Blast radius**: <1-2 lines — which files / surfaces / pods / users this touches>

---

## 1. Task

<One-paragraph restatement of the ticket. What's the change? What addenda (A1-A10) are at play?>

## 2. Spec — acceptance criteria

- [ ] AC-1: <falsifiable statement>
- [ ] AC-2: ...
- [ ] AC-3: ...

Out of scope for this ticket: <list explicitly>

## 3. Design

<Approach. If non-obvious, link an ADR under docs/decisions/. If trivial, one paragraph. Note alternatives considered + why rejected.>

## 4. Code

| File | Lines | Change |
|---|---|---|
| `app/...` | NN-NN | <one-line summary> |

## 5. Eval / Test

```
<command run>
```

```
<output>
```

## 6. Red team

<Adversarial review notes. At minimum: ran /review on the diff. What could break? What did spec miss? What edge cases are NOT covered? What's the failure mode if this code is wrong in production?>

## 7. Fix

<If red team found something: fix description, re-run output. If clean: "No findings — clean.">

## 8. Deploy

- [ ] Commit: <SHA after commit>
- [ ] CI green: <link / status>
- [ ] `.context/active_tasks.md` updated
- [ ] Ratchet baseline updated (if applicable)

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| YYYY-MM-DDTHH:MMZ | — | `[Spec]` | Created |
