# IA Migration: legacy top-level routes → `/workspace/*`

**Owner**: Reviewer Frontend pod
**Status**: TMX-3600 closes the IA decision + redirect layer (this doc). Per-page content migration tracked separately.
**Addendum**: A7 (one canonical IA: `/workspace/*`).
**Last updated**: 2026-05-07

---

## Decision

**`/workspace/*` is the canonical Information Architecture for the TransMax frontend.** All authenticated UX lives under this prefix going forward. The pre-existing parallel top-level routes (`/document`, `/translate`, `/review`, `/new`, `/knowledge`, `/dashboard`, `/design-system`) are deprecated.

External links, bookmarks, and SDK URLs targeting legacy paths land inside `/workspace/*` via HTTP redirects defined in `frontend/next.config.ts`. The legacy `page.tsx` files remain on disk during the transition — Next.js redirects in `next.config.ts` preempt file-based routing — and per-page content migration tickets (below) will move the bodies and delete the legacy files.

## Why one canonical IA

Per CLAUDE.md addendum A7: two IAs is two surfaces to validate, two themes to maintain, two ways for a reviewer to get lost. One canonical IA is a precondition for the design-system v1 (TMX-3601) and for the validation-pack work (E6).

## Redirect table

The redirect map is defined in `frontend/next.config.ts`. Every row's rationale is below.

| Legacy source | Destination | HTTP | Why |
|---|---|---|---|
| `/document/:docId` | `/workspace/documents/:docId` | 308 | One-to-one. Workspace already has the matching `[id]` page; only param name normalised. |
| `/new` | `/workspace/upload` | 308 | One-to-one. Upload is the entry point to the workspace pipeline. |
| `/dashboard` | `/workspace` | 308 | The workspace root IS the dashboard. No content gap. |
| `/design-system` | `/workspace/design-system` | 308 | TMX-3604: legacy page deleted, canonical lives under `/workspace/design-system` (TMX-3602-patterns demo). |
| `/translate/:jobId` | `/workspace/jobs/:jobId?mode=translate` | 308 | TMX-3603-jobs-id (Loop 27 fire 7) tightened from 307 → 308 once `/workspace/jobs/[id]` shipped. |
| `/review/:jobId` | `/workspace/jobs/:jobId?mode=review` | 308 | TMX-3603-jobs-id tightened from 307 → 308 once `/workspace/jobs/[id]` shipped. |
| `/knowledge` | `/workspace/tools` | 307 | Knowledge base maps to tools/glossary section per design v1. 307 because the IA may split into `/workspace/tools` and `/workspace/glossary` later. |

## Routes deliberately NOT redirected

| Route | Why kept at top level |
|---|---|
| `/` | Landing page; pre-auth. |
| `/login` | Auth flow; pre-auth. |

## Follow-up tickets

The IA decision is now landed. Per-page content migration is tracked as:

| Ticket | Scope |
|---|---|
| TMX-3601 | Theme unification (light default, dark via `prefers-color-scheme`) — already in Sprint 1 backlog. |
| TMX-3602 | Move `/document/[docId]/page.tsx` body into `/workspace/documents/[id]/page.tsx`; delete legacy file. |
| ~~TMX-3603~~ | ~~Build `/workspace/jobs/[id]`~~ — **CLOSED** (Loop 27 fire 7): page exists, redirects 308. |
| ~~TMX-3604~~ | ~~Decide `/design-system` fate~~ — **CLOSED**: legacy page deleted, redirected 308 to `/workspace/design-system`. |
| ~~TMX-3605~~ | ~~Internal-reference cleanup~~ — **subsumed by TMX-3600** — the 7 internal references found in the AC-7 grep audit were updated inline (Sidebar, dashboard, new, AssetsView). |

## Verification

**Build-time** (each PR via CI):
```
cd frontend && npm run build
```
Next.js validates the `redirects()` shape at build — invalid `:param` syntax, duplicate sources, or unreachable destinations fail the build.

**Post-deploy smoke** (manual or scripted):
```
curl -sIL <prod-url>/document/abc-123 | head -3   # expect 308 → /workspace/documents/abc-123
curl -sIL <prod-url>/new                | head -3   # expect 308 → /workspace/upload
curl -sIL <prod-url>/dashboard          | head -3   # expect 308 → /workspace
curl -sIL <prod-url>/translate/job-xyz  | head -3   # expect 307 → /workspace/jobs?focus=job-xyz&action=translate
curl -sIL <prod-url>/review/job-xyz     | head -3   # expect 307 → /workspace/jobs?focus=job-xyz&action=review
curl -sIL <prod-url>/knowledge          | head -3   # expect 307 → /workspace/tools
```

**Cross-references**: `.context/loops/TMX-3600.md` is the per-loop worksheet with status log + red-team notes.
