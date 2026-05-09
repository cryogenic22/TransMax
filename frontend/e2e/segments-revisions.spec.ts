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
    // aria-label. With one revision-bearing segment in the stub, exactly
    // one such note must be present.
    const notes = page.getByRole("note", { name: /tracked changes/i })
    await expect(notes).toHaveCount(1)

    // Sanity: the visible label should read 'tracked' (insertions, no
    // pure-move directional variant).
    await expect(notes.first()).toContainText(/tracked/)
    await expect(notes.first()).toContainText(/Dr\. Reviewer/)
  })
})
