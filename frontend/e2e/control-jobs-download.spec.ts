import { test, expect, type Route } from "@playwright/test"

// TMX-3604-download-toast — JobsView and documents/[id] both swallowed
// download failures with console.error("Download failed:", err). User
// clicked the download icon, the API rejected, no UX feedback —
// looked like a popup blocker. This test covers the JobsView site;
// the documents/[id] site uses the same fix and the same backend
// endpoint (api.documents.downloadTranslated).

const STUB_DOC_ID = "stub-job-download-fail"

const STUB_DOC_LIST = {
  items: [
    {
      id: STUB_DOC_ID,
      name: "download-fail-fixture.docx",
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

test.describe("Control Tower > Jobs download UX (TMX-3604-download-toast)", () => {
  test("shows toast.error when GET /download-translated fails", async ({ page }) => {
    await page.route("**/api/**", async (route: Route) => {
      const url = route.request().url()
      const method = route.request().method()

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
      if (method === "GET" && url.endsWith(`/api/documents/${STUB_DOC_ID}/segments`)) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([]),
        })
        return
      }
      if (
        method === "GET" &&
        url.endsWith(`/api/documents/${STUB_DOC_ID}/download-translated`)
      ) {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({
            detail: "TMX-3604-download-test: export pipeline temporarily offline",
          }),
        })
        return
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({}),
      })
    })

    await page.goto("/workspace/control?tab=jobs")
    await page.waitForLoadState("networkidle")

    // Click the download icon on the row.
    await page.locator('[title="Download translated document"]').first().click()

    // Toast must surface the actual server detail.
    await expect(
      page.getByText(/export pipeline temporarily offline/)
    ).toBeVisible()
  })
})
