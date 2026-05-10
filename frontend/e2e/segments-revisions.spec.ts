import { test, expect, type Route } from "@playwright/test"

// TMX-3702-e2e — page-level integration test that the RevisionIndicator
// renders when a segment carries DOCX tracked-change metadata, and stays
// hidden when it doesn't. Covers the gap between the component-level
// vitest (which only sees the props in isolation) and the backend
// contract test (which only verifies the wire shape).

const STUB_DOC_ID = "stub-doc-revisions"
const STUB_DOC = {
  id: STUB_DOC_ID,
  name: "tracked-changes-fixture.docx",
  file_type: "docx",
  status: "translated",
  source_language: "en",
  target_language: "de",
  glossary_id: null,
  segment_count: 2,
  word_count: 24,
  page_count: 1,
  confidence_score: 0.92,
  total_tokens: 320,
  total_cost_usd: 0.0042,
  created_at: "2026-05-09T20:00:00Z",
  updated_at: "2026-05-09T20:30:00Z",
}

const STUB_SEGMENTS = [
  {
    id: "seg-with-revisions",
    document_id: STUB_DOC_ID,
    order_index: 1,
    source_text: "Take the medication twice daily with food.",
    translated_text: "Nehmen Sie das Medikament zweimal täglich mit Nahrung ein.",
    confidence_score: 0.91,
    status: "translated",
    gate_results: {},
    validation_score: null,
    reverse_translation: null,
    element_meta: {
      revisions: {
        has_insertions: true,
        has_deletions: false,
        has_moves: false,
        has_moves_from: false,
        has_moves_to: false,
        authors: ["Dr. Reviewer"],
        dates: ["2026-04-01T10:00:00Z"],
      },
    },
    created_at: "2026-05-09T20:00:00Z",
    updated_at: "2026-05-09T20:00:00Z",
  },
  {
    id: "seg-without-revisions",
    document_id: STUB_DOC_ID,
    order_index: 2,
    source_text: "Do not exceed 1000 mg in 24 hours.",
    translated_text: "Überschreiten Sie nicht 1000 mg in 24 Stunden.",
    confidence_score: 0.94,
    status: "translated",
    gate_results: {},
    validation_score: null,
    reverse_translation: null,
    element_meta: null,
    created_at: "2026-05-09T20:00:00Z",
    updated_at: "2026-05-09T20:00:00Z",
  },
  {
    id: "seg-heavily-edited",
    document_id: STUB_DOC_ID,
    order_index: 3,
    source_text: "Multi-revision segment used to verify the count threshold.",
    translated_text: "Stark bearbeitetes Segment.",
    confidence_score: 0.85,
    status: "translated",
    gate_results: {},
    validation_score: null,
    reverse_translation: null,
    element_meta: {
      // TMX-3702-counts: total 20 marks should trigger '20 changes' display.
      revisions: {
        has_insertions: true,
        has_deletions: true,
        has_moves: false,
        has_moves_from: false,
        has_moves_to: false,
        n_insertions: 12,
        n_deletions: 8,
        n_moves_from: 0,
        n_moves_to: 0,
        authors: ["Senior Author", "QC Lead"],
        dates: ["2026-04-01T10:00:00Z", "2026-04-08T16:30:00Z"],
      },
    },
    created_at: "2026-05-09T20:00:00Z",
    updated_at: "2026-05-09T20:00:00Z",
  },
]

async function stubBackend(route: Route) {
  const url = route.request().url()
  if (url.endsWith(`/api/documents/${STUB_DOC_ID}`)) {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(STUB_DOC),
    })
    return
  }
  if (url.endsWith(`/api/documents/${STUB_DOC_ID}/segments`)) {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(STUB_SEGMENTS),
    })
    return
  }
  if (url.includes("/api/dashboard/agent-activity-by-job/")) {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ activities: [], audit_id: null }),
    })
    return
  }
  // Catch-all for any other API call — return an empty success.
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({}),
  })
}

test.describe("RevisionIndicator page-level integration (TMX-3702-e2e)", () => {
  test("renders on segments with element_meta.revisions; hides on those without", async ({
    page,
  }) => {
    await page.route("**/api/**", stubBackend)
    await page.goto(`/workspace/jobs/${STUB_DOC_ID}?mode=review`)
    await page.waitForLoadState("networkidle")

    // The pill is identified by role='note' with the segment-tracked-changes
    // aria-label. Two of the three stubbed segments carry revisions
    // (single-author insertion + heavily-edited 20-mark fixture); the
    // no-revisions middle segment must NOT render the pill.
    const notes = page.getByRole("note", { name: /tracked change/i })
    await expect(notes).toHaveCount(2)

    // Sanity: the first revision-bearing pill reads 'tracked' (insertions
    // path, no pure-move directional variant) and names the author.
    await expect(notes.first()).toContainText(/tracked/)
    await expect(notes.first()).toContainText(/Dr\. Reviewer/)
  })

  test("shows '20 changes' count on the heavily-edited segment (TMX-3702-counts)", async ({
    page,
  }) => {
    await page.route("**/api/**", stubBackend)
    await page.goto(`/workspace/jobs/${STUB_DOC_ID}?mode=review`)
    await page.waitForLoadState("networkidle")

    // The 12 insertions + 8 deletions fixture should trigger the count
    // segment in the pill. Single-edit pill above this one must NOT show
    // a count.
    await expect(page.getByText(/20 changes/)).toBeVisible()

    // Verify the threshold: the single-author single-insertion fixture
    // should NOT carry a 'changes' count (count = 1 < threshold of 2).
    const allCounts = page.getByText(/\d+ changes/)
    await expect(allCounts).toHaveCount(1)
  })
})

// ── TMX-3603-jobs-id-err: real fetch errors must be visible ─────────────

test.describe("Workspace jobs page error UX (TMX-3603-jobs-id-err)", () => {
  test("renders the actual server error when document fetch fails (not 'Job not found.')", async ({
    page,
  }) => {
    // Simulate a backend 500 — common during deploys, DB hiccups, OOM.
    // Pre-fix code silently swallowed this and showed "Job not found.",
    // misleading reviewers into thinking the doc was deleted.
    await page.route("**/api/**", async (route: Route) => {
      const url = route.request().url()
      if (url.endsWith(`/api/documents/${STUB_DOC_ID}`)) {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "TMX-3603-test: simulated upstream failure" }),
        })
        return
      }
      // Other API calls: harmless empty success.
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({}),
      })
    })

    await page.goto(`/workspace/jobs/${STUB_DOC_ID}?mode=review`)
    await page.waitForLoadState("networkidle")

    // The actual server-supplied detail must surface — proving we no
    // longer mask 5xx as 404.
    await expect(
      page.getByText(/TMX-3603-test: simulated upstream failure/)
    ).toBeVisible()
    // And the misleading static fallback must NOT appear.
    await expect(page.getByText("Job not found.")).toHaveCount(0)
  })

  test("doc loads + segments-error banner when only segments fail", async ({
    page,
  }) => {
    // Doc fetch succeeds, segments fetch returns 500. The page should
    // render the doc header (still useful) AND a per-section error
    // banner so the reviewer knows something is wrong with segments.
    await page.route("**/api/**", async (route: Route) => {
      const url = route.request().url()
      if (url.endsWith(`/api/documents/${STUB_DOC_ID}`)) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(STUB_DOC),
        })
        return
      }
      if (url.endsWith(`/api/documents/${STUB_DOC_ID}/segments`)) {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "TMX-3603-test: segments index unavailable" }),
        })
        return
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({}),
      })
    })

    await page.goto(`/workspace/jobs/${STUB_DOC_ID}?mode=review`)
    await page.waitForLoadState("networkidle")

    // Doc header is visible (graceful degradation).
    await expect(
      page.getByRole("heading", { name: /tracked-changes-fixture\.docx/ })
    ).toBeVisible()
    // Segments error banner uses role='status' (polite) so SR users
    // hear it after the doc header. Identified by its aria-label since
    // role='alert' would collide with Next.js's route-change announcer.
    const banner = page.getByRole("status", { name: /segments failed to load/i })
    await expect(banner).toBeVisible()
    await expect(banner).toContainText(/segments index unavailable/)
  })

  test("renders agent-activity error banner when poll fails (TMX-3603-agents-err)", async ({
    page,
  }) => {
    // Doc + segments OK; agent-activity polling 500. The agent lanes
    // would otherwise render empty silently — indistinguishable from
    // "no agents running yet". Banner makes the failure visible.
    await page.route("**/api/**", async (route: Route) => {
      const url = route.request().url()
      if (url.endsWith(`/api/documents/${STUB_DOC_ID}`)) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(STUB_DOC),
        })
        return
      }
      if (url.endsWith(`/api/documents/${STUB_DOC_ID}/segments`)) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(STUB_SEGMENTS),
        })
        return
      }
      if (url.includes("/api/dashboard/agent-activity-by-job/")) {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "TMX-3603-agents-test: activity feed offline" }),
        })
        return
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({}),
      })
    })

    // Translate mode renders AgentLanes — best place to verify the
    // agent-activity error surfaces. Review mode doesn't show lanes.
    await page.goto(`/workspace/jobs/${STUB_DOC_ID}?mode=translate`)
    await page.waitForLoadState("networkidle")

    const banner = page.getByRole("status", { name: /agent activity feed failed to load/i })
    await expect(banner).toBeVisible()
    // Hook returns Error("HTTP 500") on non-OK; render that message.
    await expect(banner).toContainText(/HTTP 500/)
  })
})
