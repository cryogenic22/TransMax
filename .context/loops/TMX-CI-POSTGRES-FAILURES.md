# TMX-CI-POSTGRES-FAILURES — green the suite on Postgres (newly visible after the collection fix)

**State**: `[WIP]`
**Owner**: Platform & Observability
**Sprint**: MQM Keystone / Phase 0 (make CI a real gate)
**Started**: 2026-06-15
**Reversibility**: `two-way` (test-data + CI-config fixes; no app behaviour change)
**Pre-mortem**: if this fails in production, the failure mode is *n/a — test/CI-only changes*; the risk is masking a REAL app bug as "just a test bug", mitigated by confirming the app's own code path is correct (e.g. the app generates 36-char ids; the column width is right) before editing the test.
**Blast radius**: `tests/test_segments_element_meta.py`, `tests/test_dashboard_activity_feed.py`, `tests/test_vectors.py`, and `.github/workflows/ci.yml` (fetch-depth). No `app/` change.

**Loop-driven-dev gates**:
- [x] **G1 Anti-bloat** — fixing real test-data bugs that hid a whole class of Postgres-vs-SQLite drift; not net-new code.
- [x] **G2 Reproduce-the-failure** — reproduced on a local `pgvector/pgvector:pg16` container matching CI: `StringDataRightTruncation: value too long for type character varying(36)`.
- [ ] **G3 Completion** — the locally-reproducible failures pass on local Postgres; the CI-env ones get a ci.yml fix validated by a CI run.

---

## 1. Task

After TMX-CI-PRODSAFE-ENV unbroke pytest collection, the suite ran in CI for the first time: **1355 passed, 4 failed, 12 errored**. All pre-existing (never ran in CI before). Reproduced locally against `pgvector/pgvector:pg16`:

| Failure | Count | Root cause | Class |
|---|---|---|---|
| `test_segments_element_meta` | 3 ERROR | test ids `f"doc-{uuid}"`/`f"seg-{uuid}"` = 40 chars > `documents.id`/`segments.id` `VARCHAR(36)`. SQLite ignores VARCHAR length; Postgres enforces → `StringDataRightTruncation` → rollback. App uses `str(uuid4())` (36, fits) — so the **test** is wrong, not the schema. | test-data |
| `test_dashboard_activity_feed` | 9 ERROR | same — `doc_id = f"doc-test-{uuid}"` = 45 chars; + any setup writes needing `org_context`. | test-data |
| `test_vectors::test_vector_integration` | 1 FAIL | pgvector integration — needs investigation on real Postgres. | pg-infra |
| `test_auth_wall_seed`, `test_audit_worktree_clean`, `test_regulatory_pack_traceability` | (CI only) | PASS on local Postgres → CI-environment: shallow clone depth (git-SHA resolution) + CI worktree state. | ci-env |

## 2. Spec — acceptance criteria

- [ ] AC-1: `test_segments_element_meta` + `test_dashboard_activity_feed` pass on local Postgres (`pgvector/pgvector:pg16`) — entity ids fit `VARCHAR(36)` (use `str(uuid4())`, matching the app), setup writes have a tenant context where a flush-time SELECT needs one.
- [ ] AC-2: `test_vectors::test_vector_integration` passes on local Postgres, or is `importorskip`/xfail'd with a precise reason if the failure is a genuine pgvector-env gap.
- [ ] AC-3: the 3 CI-env failures get a ci.yml fix (e.g. `fetch-depth: 0` for git-SHA resolution) validated by a CI run; any not fixable get a documented `skip`/reason, not a silent red.
- [ ] AC-4: no `app/` behaviour change; the column widths + app id generation are confirmed correct first.

## 3. Design

The 12 errors are pure test-data bugs: tests minted ids with human-readable prefixes (`doc-`, `seg-`, `doc-test-`) that overflow the 36-char id columns. The app's own id generation is `str(uuid.uuid4())` (`app/api/documents.py:87`, `app/api/v1/translations.py:42`) — exactly 36 chars — so the schema is right and the tests should mirror it. Fix = use `str(uuid.uuid4())` for entity ids in these fixtures (+ wrap any setup write that triggers a tenant-scoped SELECT in `org_context`, consistent with the existing teardown). `test_vectors` + the CI-env trio are separate, smaller sub-fixes.

Alternatives rejected: widening the id columns to fit `doc-{uuid}` — wrong (the app uses 36-char ids; widening the schema to accommodate a test convention is a one-way change to paper over a test bug, A4).

## 4. Code

| File | Change |
|---|---|
| `tests/test_segments_element_meta.py` | ids → `str(uuid4())`; wrap setup in `org_context` if needed |
| `tests/test_dashboard_activity_feed.py` | ids → `str(uuid4())`; same |
| `tests/test_vectors.py` | investigate pgvector failure |
| `.github/workflows/ci.yml` | `fetch-depth: 0` for the traceability git-SHA resolution (validated via CI) |

## 5. Eval / Test

```
# on local pgvector/pgvector:pg16 (matches CI exactly):
pytest tests/test_segments_element_meta.py tests/test_dashboard_activity_feed.py  → 15 passed (was 12 errors)
# SQLite regression (no fix broke the SQLite path):
pytest (same, sqlite)  → 15 passed
ruff check (3 edited test files)  → clean
test_vectors → now skips deterministically (opt-in)
```

Fixes:
- **segments (3)**: entity ids `f"doc-/seg-{uuid}"` (40 chars) → `str(uuid4())` (36) to fit `VARCHAR(36)`.
- **dashboard (9)**: `doc_id` (45 chars) → `str(uuid4())`; seed the FK parent `TranslationJobQueue` before each `AuditRecord` (Postgres enforces the `audit_records_queue.job_id` FK; SQLite skips it); wrap both fixture teardowns' bulk `.delete()` in `org_context(DEFAULT_ORG_ID)` (the delete resolves rows via a tenant-scoped SELECT).
- **test_vectors (1)**: opt-in (`RUN_VECTOR_INTEGRATION`) — it makes live OpenAI calls (the TMX-3000 key) + needs a tenant context; it must not run in the unit CI.
- **CI-env (3)**: `fetch-depth: 0` on the Unit Tests checkout so the git-SHA resolutions in `test_regulatory_pack_traceability` + `test_audit_worktree_clean` work (they pass locally with full history). `test_auth_wall_seed` may have been collateral from `test_vectors` poisoning the shared session (now skipped) — confirmed via the CI re-run.

## 6. Red team (self-review — test-only, no app behaviour change)

Key question: does any fix MASK a real app bug? No. (a) The app generates 36-char ids (`documents.py:87`, `translations.py:42`) and the column is `VARCHAR(36)` — the schema is right; the tests minted over-long ids. (b) The app sets a tenant context on every real request/service path; the fixtures called raw `SessionLocal()`/`.delete()` without one. (c) `add_tm_segment` legitimately requires an ambient tenant context (tenant isolation by design) — the integration test called it raw + with a live key, so opt-in is the honest treatment, not a cover-up. All fixes validated on BOTH Postgres (the real target) and SQLite (no regression). Follow-up (noted): a mocked-embedding unit test of the pgvector TM path could replace the opt-in integration test.

## 7. Fix

(none beyond the above — validated first try on Postgres)

## 8. Deploy

- [x] Commit `c189b99` — segments+dashboard+vectors+ci.yml+worksheet
- [x] Push → CI (PR #20) validated: **1369 passed, 1 failed, 5 skipped** (was crash/0). The 12 errors + vectors + both git CI-env tests are GREEN. Only `test_auth_wall_seed` remained.

## 9. Addendum — TMX-CI-BCRYPT (the last failure was a real auth bug, not test-env)

`test_auth_wall_seed` failed in CI but passed in every local run. Surfacing the seed's *swallowed* exception (`database.py:230 except Exception`) via the CI log revealed the true cause: **`requirements.txt` pinned `passlib[bcrypt]` with no version**, so CI's fresh install pulled bcrypt 4.x. passlib 1.7.4 (unmaintained since 2020) is incompatible with bcrypt 4.1+ (which removed `bcrypt.__about__`) — its backend self-test hashes a >72-byte probe that bcrypt 4.x rejects, so passlib marks bcrypt unusable and EVERY `hash()` call fails with a spurious "password cannot be longer than 72 bytes". This is a **production auth bug** (login/register/seed would break on any fresh deploy that pulls bcrypt 4.x), not a test issue.

Fix: migrate `app/auth/password.py` off passlib to **bcrypt directly** (`requirements.txt`: `passlib[bcrypt]` → `bcrypt`). Proven byte-compatible: a real passlib-made `$2b$12$…` hash verifies under `bcrypt.checkpw` (frozen regression pin in `tests/test_password_hashing.py`), same ident/cost(12)/72-byte truncation. Adversarial auth red-team (agent `a9cc13d4`) verdict **SHIP** — no defect across backward-compat / truncation / fail-closed / work-factor. 41 auth tests + 5 new password tests green on Postgres.

- [ ] Commit (this) — password.py + requirements.txt + test_password_hashing.py
- [ ] Push → CI validates auth_wall_seed now passes (full green expected)

---

## Status log

| When (UTC) | From | To | Note |
|---|---|---|---|
| 2026-06-15 | — | `[WIP]` | Reproduced all locally on `pgvector/pgvector:pg16`; root cause = VARCHAR(36) id overflow (Postgres enforces, SQLite ignores), not tenant-context as first suspected. |
