import { test, expect } from "@playwright/test"

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8001"

test.describe("Jobs detail (live integration)", () => {
  test("GET /api/dashboard/agent-activity-by-job/<unknown> returns empty shape", async ({
    request,
  }) => {
    // Random job_id — backend should respond 200 with empty activities
    // and audit_id=null (not 404). TMX-3603-jobs-id wire-up.
    const res = await request.get(
      `${BACKEND}/api/dashboard/agent-activity-by-job/nonexistent-job-${Date.now()}`
    )
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty("activities")
    expect(body).toHaveProperty("audit_id")
    expect(Array.isArray(body.activities)).toBe(true)
    expect(body.audit_id).toBeNull()
  })

  test("GET /api/dashboard/agent-activity/<unknown-uuid> returns empty activities", async ({
    request,
  }) => {
    // The audit-id-direct endpoint also handles unknown ids gracefully.
    const res = await request.get(
      `${BACKEND}/api/dashboard/agent-activity/00000000-0000-0000-0000-000000000000`
    )
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty("activities")
    expect(Array.isArray(body.activities)).toBe(true)
  })

  test("/workspace/jobs/[id] route renders without crash for unknown id", async ({
    page,
  }) => {
    const consoleErrors: string[] = []
    page.on("pageerror", err => consoleErrors.push(err.message))
    await page.goto("/workspace/jobs/sample-job-not-real")
    await page.waitForLoadState("networkidle")
    // Page should render the empty / not-found message; no React errors.
    expect(consoleErrors).toEqual([])
  })

  test("/workspace/jobs/[id]?mode=review renders the review tab", async ({
    page,
  }) => {
    const consoleErrors: string[] = []
    page.on("pageerror", err => consoleErrors.push(err.message))
    await page.goto("/workspace/jobs/sample-job-not-real?mode=review")
    await page.waitForLoadState("networkidle")
    expect(consoleErrors).toEqual([])
  })
})

test.describe("Security headers (TMX-3615)", () => {
  test("frontend serves CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy on /", async ({
    request,
  }) => {
    const res = await request.get("/", { maxRedirects: 0 })
    const headers = res.headers()
    // CSP
    expect(headers["content-security-policy"]).toBeTruthy()
    expect(headers["content-security-policy"]).toContain("default-src 'self'")
    expect(headers["content-security-policy"]).toContain("frame-ancestors 'none'")
    // HSTS
    expect(headers["strict-transport-security"]).toBe("max-age=31536000; includeSubDomains; preload")
    // Clickjacking
    expect(headers["x-frame-options"]).toBe("DENY")
    // MIME sniff
    expect(headers["x-content-type-options"]).toBe("nosniff")
    // Referrer
    expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin")
    // Permissions
    expect(headers["permissions-policy"]).toContain("camera=()")
    expect(headers["permissions-policy"]).toContain("geolocation=()")
  })

  test("security headers ride to the redirect destination", async ({ request }) => {
    // /dashboard 308-redirects to /workspace; following the chain, the
    // final response (the canonical /workspace page) must still carry the
    // headers. Next.js's headers() config applies at the destination, not
    // the 308 itself, so this is the user-facing contract.
    const res = await request.get("/dashboard")
    expect(res.status()).toBe(200)
    expect(res.headers()["content-security-policy"]).toBeTruthy()
    expect(res.headers()["strict-transport-security"]).toBeTruthy()
    expect(res.headers()["x-frame-options"]).toBe("DENY")
  })
})
