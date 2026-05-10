import { test, expect, type Route } from "@playwright/test"

// TMX-3604-tools-toast — workspace/tools/page had 5 console.error
// swallows on user actions: positive feedback, Black Book correction,
// Quality Audit, back-translate, and matrix. All five share a common
// shape: user clicks a button, the API rejects, the catch logs to
// console only.
//
// This test exercises the Quality Audit path because it has the
// simplest UI flow (paste source + translation, click button) and
// proves the toast wiring works. The other 4 sites use the same fix.

test.describe("Tools page action UX (TMX-3604-tools-toast)", () => {
  test("shows toast.error when Quality Audit POST fails", async ({ page }) => {
    await page.route("**/api/**", async (route: Route) => {
      const url = route.request().url()
      const method = route.request().method()
      if (method === "POST" && url.endsWith("/api/tools/audit")) {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({
            detail: "TMX-3604-tools-test: audit service unavailable",
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

    await page.goto("/workspace/tools")
    await page.waitForLoadState("networkidle")

    // Quality Auditor is the default tab — fill source + translation.
    const textareas = page.locator("textarea")
    await textareas.nth(0).fill("Take 100 mg twice a day.")
    await textareas.nth(1).fill("Prendre 100 mg une fois par jour.")

    // Click Run Quality Checks.
    await page.getByRole("button", { name: /run quality checks/i }).click()

    // Toast must surface the actual server detail.
    await expect(
      page.getByText(/audit service unavailable/)
    ).toBeVisible()
  })
})
