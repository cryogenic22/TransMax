import { test, expect } from "@playwright/test"

test.describe("Frontend dashboard (live integration)", () => {
  test("workspace root renders without an offline-backend banner", async ({
    page,
  }) => {
    const consoleErrors: string[] = []
    page.on("pageerror", err => consoleErrors.push(err.message))

    await page.goto("/workspace")
    // Wait for hydration / first data fetch.
    await page.waitForLoadState("networkidle")

    // The frontend's Sidebar / dashboard variants render network-error states
    // with "offline" / "unable to reach" copy. None of those strings should
    // appear when the backend is live.
    const body = await page.locator("body").textContent()
    expect(body?.toLowerCase()).not.toContain("backend offline")
    expect(body?.toLowerCase()).not.toContain("unable to reach api")
    expect(consoleErrors).toEqual([])
  })

  test("/dashboard legacy URL redirects to /workspace and renders", async ({
    page,
  }) => {
    const response = await page.goto("/dashboard")
    expect(response?.status()).toBeLessThan(400)
    await expect(page).toHaveURL(/\/workspace$/)
  })
})
