import { test, expect, type Route } from "@playwright/test"

// TMX-3604-doc-review-err — the workspace/documents/[id] page suppressed
// fetch errors with `} catch { setDocument(null) }`, rendering only the
// generic "Document not found" string for any failure mode (500, network,
// AuthN). Reviewer landing here from JobsView / Sidebar / a translation
// toast had no signal whether the doc was deleted, the API was down, or
// something else. Final A3 sweep ticket.

const STUB_DOC_ID = "stub-doc-review-err"

test.describe("Document review page error UX (TMX-3604-doc-review-err)", () => {
  test("renders the actual server error when document fetch fails", async ({
    page,
  }) => {
    // Simulate a backend 500 — the page must surface the real message,
    // not silently fall through to "Document not found".
    await page.route("**/api/**", async (route: Route) => {
      const url = route.request().url()
      if (url.endsWith(`/api/documents/${STUB_DOC_ID}`)) {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "TMX-3604-doc-test: review service offline" }),
        })
        return
      }
      // Any other call: harmless empty success.
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({}),
      })
    })

    await page.goto(`/workspace/documents/${STUB_DOC_ID}`)
    await page.waitForLoadState("networkidle")

    // The actual server-supplied detail must surface.
    await expect(
      page.getByText(/TMX-3604-doc-test: review service offline/)
    ).toBeVisible()
    // And the misleading fallback must NOT be the only message visible
    // (it can appear secondarily; what matters is that the real error
    // is on the page).
  })
})
