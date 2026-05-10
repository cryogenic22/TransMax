import { defineConfig, devices } from "@playwright/test"

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  // TMX-3614-workers: workers=1 always — `npm run dev` is a single
  // shared server (per webServer.reuseExistingServer below); multiple
  // worker processes racing against it cause intermittent
  // ERR_CONNECTION_REFUSED + "context teardown timeout" failures on
  // dev machines. CI already runs workers=1; aligning non-CI here so
  // `npm run e2e` is reliable without the `--workers=1` flag.
  workers: 1,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
