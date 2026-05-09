import { defineConfig, devices } from "@playwright/test"
import path from "path"

// Loop 15 — frontend ↔ backend integration tests.
//
// Spawns BOTH uvicorn (port 8001) and Next dev (port 3000) as Playwright
// webServer entries. Tests in `e2e-integration/` exercise the live stack:
// real CORS, real serialisation, real DB. No LLM calls (those live in the
// eval harness so CI doesn't burn provider budget).

const projectRoot = path.resolve(__dirname, "..")

export default defineConfig({
  testDir: "./e2e-integration",
  fullyParallel: false, // shared backend state — keep tests serial
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "list",
  outputDir: "test-results-integration",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    extraHTTPHeaders: {
      // Tag every Playwright-issued HTTP call so backend logs / observability
      // can distinguish synthetic load from real users.
      "X-Test-Run": "playwright-integration",
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      // FastAPI backend — uvicorn from project root so `app.main:app` resolves.
      command: "python -m uvicorn app.main:app --port 8001 --host 127.0.0.1",
      url: "http://127.0.0.1:8001/health",
      cwd: projectRoot,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        APP_ENV: "test",
        AUTH_MODE: "none",
        OPENAI_API_KEY: "test-stub",
      },
    },
    {
      // Next dev — pointed at the integration backend.
      command: "npm run dev",
      url: "http://localhost:3000",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        NEXT_PUBLIC_API_URL: "http://127.0.0.1:8001",
        NEXT_PUBLIC_AUTH_MODE: "none",
      },
    },
  ],
})
