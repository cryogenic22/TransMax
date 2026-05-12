import { test, expect } from "@playwright/test"

// TMX-3618 — visual-snapshot regression test for /workspace/design-system.
// Catches design-token drift (TMX-3601 bumped colours/spacing without
// updating both :root and .dark; this test flags those slips before
// they reach production).
//
// Cross-platform baselines:
//   - First-run on each OS generates a per-OS baseline file
//     (e.g. main-content-chromium-win32.png, ...-linux.png).
//   - Playwright will FAIL if the baseline is missing — that's the
//     intended signal that whoever's running the test on a new OS
//     should run `npm run e2e -- design-system-visual --update-snapshots`,
//     review the generated image, and commit it.
//   - `maxDiffPixelRatio: 0.05` (5%) tolerates antialiasing + minor
//     font rendering differences without missing real regressions.
//
// To regenerate after intentional design changes:
//   npm run e2e -- design-system-visual.spec.ts --update-snapshots

test.describe("Design system visual regression (TMX-3618)", () => {
  test("renders main content area pixel-stable", async ({ page }) => {
    // Freeze the page clock so REVISION_FIXTURES' relative-time labels
    // ("3d ago" etc.) don't drift day-to-day. Pinned to the same
    // 2026-05-10 reference used in other snapshot fixtures.
    await page.clock.install({ time: new Date("2026-05-10T00:00:00Z") })

    await page.goto("/workspace/design-system")
    // `networkidle` is fragile when `page.clock.install` freezes the
    // page clock (pollers using setInterval never quiesce). Use `load`
    // instead — by the time the load event fires, the design-system
    // page (no async data fetching, only static fixtures) is render-
    // stable enough for the snapshot.
    await page.waitForLoadState("load")
    await page.evaluate(() => document.fonts.ready)

    await expect(page).toHaveScreenshot("design-system-page.png", {
      // Single platform-agnostic filename via toHaveScreenshot's
      // explicit name argument; per-OS baselines still happen via
      // Playwright's default suffix because the project defines
      // chromium as the only project name.
      maxDiffPixelRatio: 0.05,
      animations: "disabled",
      caret: "hide",
      // Mask the relative-time `<time>` elements as belt-and-braces
      // even with the clock frozen — sonner's render order can vary.
      mask: [page.locator("time")],
      fullPage: true,
    })
  })
})
