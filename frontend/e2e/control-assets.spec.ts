import { test, expect, type Route } from "@playwright/test"

// TMX-3604-assets-err — Trust Center > Assets tab must distinguish a
// real "no rules in the system" empty state from a "backend down"
// failure state. Pre-fix the per-promise .catch(() => []) collapsed
// both into "0 / 0 / 0" — a regulator auditing rule coverage gets
// misled. Same A3 class as TMX-3603-jobs-id-err.

test.describe("Control Tower > Assets error UX (TMX-3604-assets-err)", () => {
  test("renders error banner + '—' cards when listRules fails", async ({
    page,
  }) => {
    await page.route("**/api/**", async (route: Route) => {
      const url = route.request().url()
      if (url.includes("/api/knowledge/rules")) {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "TMX-3604-test: rules service unavailable" }),
        })
        return
      }
      if (url.includes("/api/knowledge/glossaries")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([]),
        })
        return
      }
      // Catch-all for any other API call.
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({}),
      })
    })

    await page.goto("/workspace/control?tab=assets")
    await page.waitForLoadState("networkidle")

    // Banner with the real server error visible.
    const banner = page.getByRole("status", { name: /assets failed to load/i })
    await expect(banner).toBeVisible()
    await expect(banner).toContainText(/rules service unavailable/)

    // The two rule cards (Translation Rules, Pending Review) display
    // "—" — distinct from a legitimate "0" empty state.
    const dashCells = page.getByText("—", { exact: true })
    await expect(dashCells.first()).toBeVisible()

    // Sanity: the static "Active in Black Book" subtitle still renders
    // (page didn't crash; failure is degraded-state, not full error).
    await expect(page.getByText(/active in black book/i)).toBeVisible()
  })

  test("renders 0/0/0 with no banner on legitimate empty state", async ({
    page,
  }) => {
    // All three knowledge endpoints succeed but return empty arrays —
    // the company genuinely has no rules / glossaries yet.
    await page.route("**/api/**", async (route: Route) => {
      const url = route.request().url()
      if (url.includes("/api/knowledge/")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([]),
        })
        return
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({}),
      })
    })

    await page.goto("/workspace/control?tab=assets")
    await page.waitForLoadState("networkidle")

    // No error banner — this is a legitimate empty state.
    await expect(
      page.getByRole("status", { name: /assets failed to load/i })
    ).toHaveCount(0)

    // Each card shows "0" (not "—"). Three "0" values — one per card.
    const zeros = page.getByText("0", { exact: true })
    await expect(zeros).toHaveCount(3)
  })
})
