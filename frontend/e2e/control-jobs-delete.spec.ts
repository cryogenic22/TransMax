import { test, expect, type Route } from "@playwright/test"

// TMX-3604-delete-toast — JobsView delete handler used to swallow
// errors with console.error("Delete failed:", err). User clicked
// Delete in the confirmation dialog, the API rejected it, the modal
// closed, and the doc stayed in the list with no UX feedback.
// Mutation-error analogue of the silent-fallback fetch sweep.

const STUB_DOC_ID = "stub-job-delete-fail"

const STUB_DOC_LIST = {
  items: [
    {
      id: STUB_DOC_ID,
      name: "delete-fail-fixture.docx",
      file_type: "docx",
      status: "translated",
      source_language: "en",
      target_language: "de",
      glossary_id: null,
      segment_count: 4,
      word_count: 80,
      page_count: 1,
      confidence_score: 0.92,
      total_tokens: 320,
      total_cost_usd: 0.0042,
      created_at: "2026-05-09T20:00:00Z",
      updated_at: "2026-05-09T20:30:00Z",
    },
  ],
  total: 1,
  page: 1,
  page_size: 20,
}

test.describe("Control Tower > Jobs delete UX (TMX-3604-delete-toast)", () => {
  test("shows toast.error when DELETE fails", async ({ page }) => {
    await page.route("**/api/**", async (route: Route) => {
      const url = route.request().url()
      const method = route.request().method()

      // Document list (so the row renders).
      if (
        method === "GET" &&
        url.includes("/api/documents") &&
        !url.includes(`/api/documents/${STUB_DOC_ID}`)
      ) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(STUB_DOC_LIST),
        })
        return
      }

      // Segments fetch for translated count enrichment in JobsView.
      if (method === "GET" && url.endsWith(`/api/documents/${STUB_DOC_ID}/segments`)) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([]),
        })
        return
      }

      // The mutation under test.
      if (method === "DELETE" && url.includes(`/api/documents/${STUB_DOC_ID}`)) {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({
            detail: "TMX-3604-delete-test: tombstone write rejected",
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

    await page.goto("/workspace/control?tab=jobs")
    await page.waitForLoadState("networkidle")

    // Open the delete dialog from the row's trash icon.
    await page.locator('[title="Delete document"]').first().click()

    // Confirm: the dialog renders the doc name.
    await expect(
      page.getByRole("heading", { name: /delete document/i })
    ).toBeVisible()

    // Click the final Delete button in the dialog.
    await page.getByRole("button", { name: /^delete$/i }).click()

    // Toast must appear with the actual server error. Sonner renders
    // toasts in a portal at top-right; getByText finds it anywhere.
    await expect(
      page.getByText(/tombstone write rejected/)
    ).toBeVisible()
  })
})
