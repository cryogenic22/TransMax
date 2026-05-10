import { test, expect, type Route } from "@playwright/test"

// TMX-3705-glossary-err — the upload form silently swallowed
// glossary-fetch failures, leaving translators with no signal that
// the selector should have been there. Same A3 class as the
// jobs-page and assets-view fixes; third application of the pattern.

test.describe("Upload page glossary fetch UX (TMX-3705-glossary-err)", () => {
  test("renders glossary-error notice when listGlossaries fails", async ({
    page,
  }) => {
    await page.route("**/api/**", async (route: Route) => {
      const url = route.request().url()
      if (url.includes("/api/knowledge/glossaries")) {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "TMX-3705-test: glossary catalog unavailable" }),
        })
        return
      }
      // Catch-all — any other API call returns harmless empty.
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({}),
      })
    })

    await page.goto("/workspace/upload")
    await page.waitForLoadState("networkidle")

    // Inline notice with the actual server error visible — proves we
    // no longer silently hide the failure.
    const notice = page.getByRole("status", { name: /glossary list failed to load/i })
    await expect(notice).toBeVisible()
    await expect(notice).toContainText(/glossary catalog unavailable/)
  })
})
