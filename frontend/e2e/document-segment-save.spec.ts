import { test, expect, type Route } from "@playwright/test"

// TMX-3604-save-toast — workspace/documents/[id] handleSaveEdit
// swallowed save errors with console.error("Failed to save:", err).
// A reviewer typing a HITL correction (which is an audit event)
// would see no signal whether the save took. Mutation-error class.

const STUB_DOC_ID = "stub-doc-save-fail"

const STUB_DOC = {
  id: STUB_DOC_ID,
  name: "save-fail-fixture.docx",
  file_type: "docx",
  status: "translated",
  source_language: "en",
  target_language: "de",
  glossary_id: null,
  segment_count: 1,
  word_count: 8,
  page_count: 1,
  confidence_score: 0.9,
  total_tokens: 100,
  total_cost_usd: 0.0001,
  created_at: "2026-05-10T04:00:00Z",
  updated_at: "2026-05-10T04:00:00Z",
}

const STUB_SEG_ID = "seg-save-fail-1"
const STUB_SEGMENTS = [
  {
    id: STUB_SEG_ID,
    document_id: STUB_DOC_ID,
    order_index: 1,
    source_text: "Take twice daily.",
    translated_text: "Zweimal täglich nehmen.",
    confidence_score: 0.9,
    status: "translated",
    gate_results: {},
    validation_score: null,
    reverse_translation: null,
    element_meta: null,
    created_at: "2026-05-10T04:00:00Z",
    updated_at: "2026-05-10T04:00:00Z",
  },
]

test.describe("Segment save UX (TMX-3604-save-toast)", () => {
  test("shows toast.error when PATCH /api/segments/:id fails", async ({ page }) => {
    await page.route("**/api/**", async (route: Route) => {
      const url = route.request().url()
      const method = route.request().method()

      if (method === "GET" && url.endsWith(`/api/documents/${STUB_DOC_ID}`)) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(STUB_DOC),
        })
        return
      }
      if (method === "GET" && url.endsWith(`/api/documents/${STUB_DOC_ID}/segments`)) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(STUB_SEGMENTS),
        })
        return
      }
      if (method === "PATCH" && url.endsWith(`/api/segments/${STUB_SEG_ID}`)) {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({
            detail: "TMX-3604-save-test: HITL correction rejected",
          }),
        })
        return
      }
      // Catch-all.
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({}),
      })
    })

    await page.goto(`/workspace/documents/${STUB_DOC_ID}`)
    await page.waitForLoadState("networkidle")

    // Switch to the Segments tab where the editable list lives.
    await page.getByRole("button", { name: /segments/i }).first().click()

    // Click the translation cell to enter edit mode (target text is the
    // visible click handler at line 760).
    await page.getByText("Zweimal täglich nehmen.").click()

    // Save — triggers PATCH which we stubbed to 500.
    await page.getByRole("button", { name: /^save$/i }).click()

    // Toast must surface the actual server detail.
    await expect(
      page.getByText(/HITL correction rejected/)
    ).toBeVisible()
  })
})
