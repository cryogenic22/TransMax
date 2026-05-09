import { test, expect } from "@playwright/test"

test.describe("Landing page", () => {
  test("renders without errors and shows TransMax branding", async ({
    page,
  }) => {
    // Mock the backend so the landing page does not flake on a missing API.
    await page.route("**/api/**", route =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true }),
      })
    )

    await page.goto("/")
    // The landing page contains the TransMax brand text in the header / hero
    // (case-insensitive — the exact heading case may evolve, the brand stays).
    await expect(page.getByText(/transmax/i).first()).toBeVisible()
  })

  test("legacy /dashboard 308-redirects to /workspace", async ({ page }) => {
    // 308 Permanent Redirect from TMX-3600 redirect map.
    const response = await page.goto("/dashboard")
    expect(response?.status()).toBeLessThan(400)
    // Followed redirect should land on /workspace.
    await expect(page).toHaveURL(/\/workspace$/)
  })

  test("legacy /new 308-redirects to /workspace/upload", async ({ page }) => {
    await page.route("**/api/**", route =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true }),
      })
    )
    const response = await page.goto("/new")
    expect(response?.status()).toBeLessThan(400)
    await expect(page).toHaveURL(/\/workspace\/upload$/)
  })

  test("legacy /design-system 308-redirects to /workspace/design-system", async ({ page }) => {
    // TMX-3604: legacy page deleted; canonical lives at /workspace/design-system.
    await page.route("**/api/**", route =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true }),
      })
    )
    const response = await page.goto("/design-system")
    expect(response?.status()).toBeLessThan(400)
    await expect(page).toHaveURL(/\/workspace\/design-system$/)
  })
})
