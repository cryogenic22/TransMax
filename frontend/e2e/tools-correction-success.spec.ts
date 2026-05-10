import { test, expect, type Route, type Dialog } from "@playwright/test"

// TMX-3604-alert-to-toast — Black Book correction submission used to
// fire `alert("Feedback submitted to Black Book!")` on success — a
// blocking dialog that intercepts focus and feels antiquated next to
// the now-toast-based failure UX. This test verifies the migration
// to toast.success: the success text must appear AND no alert dialog
// must fire.

test.describe("Black Book correction success UX (TMX-3604-alert-to-toast)", () => {
  test("toast.success appears (and no alert) when feedback POST succeeds", async ({
    page,
  }) => {
    let alertCount = 0
    page.on("dialog", async (dialog: Dialog) => {
      alertCount++
      await dialog.dismiss()
    })

    await page.route("**/api/**", async (route: Route) => {
      const url = route.request().url()
      const method = route.request().method()
      if (
        method === "POST" &&
        url.endsWith("/api/tools/translate/universal")
      ) {
        // Stub a successful translation so FeedbackControls becomes
        // visible in the bottom secondary-actions strip.
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            translated_text: "Tomar dos veces al día.",
            segments: [{ source: "Take twice daily.", target: "Tomar dos veces al día." }],
            confidence: 0.92,
            score_band: "high",
            score_breakdown: {},
            recommendations: [],
          }),
        })
        return
      }
      if (method === "POST" && url.endsWith("/api/knowledge/feedback")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ ok: true, rule_id: "rule-stub-1" }),
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

    await page.goto("/workspace")
    await page.waitForLoadState("networkidle")

    // Type source + click the primary translate button.
    const sourceArea = page.locator("textarea").first()
    await sourceArea.fill("Take twice daily.")
    // The translate button is large + primary; pattern-match on label.
    await page.locator("button:has-text('Translate')").first().click()
    await page.waitForLoadState("networkidle")

    // FeedbackControls renders after segments populate. The 👎 button
    // is identified by its title attribute (other "Issue"-textual
    // elements exist on the page so we anchor to the unique title).
    await page.locator('button[title="Report issue"]').click()

    // Fill in the suggestion + submit.
    await page.getByPlaceholder(/correct translation/i).fill("Tómelo dos veces al día.")
    await page.getByRole("button", { name: /submit rule/i }).click()

    // Toast must appear with the success text — proves we no longer
    // fire alert() on success.
    await expect(
      page.getByText(/feedback submitted to black book/i)
    ).toBeVisible()

    // No alert() call should have fired during the test.
    expect(alertCount).toBe(0)
  })
})
