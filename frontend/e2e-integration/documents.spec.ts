import { test, expect } from "@playwright/test"

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8001"

test.describe("Documents API (live integration)", () => {
  test("GET /api/documents returns a paginated list shape", async ({
    request,
  }) => {
    const res = await request.get(`${BACKEND}/api/documents`)
    expect(res.status()).toBe(200)
    const body = await res.json()
    // Backend list endpoints return { items: [...], page, page_size, total }
    // (verified live against app/api/documents.py:165). The contract is the
    // shape, not the count — DBs populated by prior runs are valid.
    expect(body).toHaveProperty("items")
    expect(Array.isArray(body.items)).toBe(true)
    expect(body).toHaveProperty("total")
    expect(typeof body.total).toBe("number")
  })

  test("GET /api/documents/non-existent-id returns 404", async ({
    request,
  }) => {
    const res = await request.get(`${BACKEND}/api/documents/non-existent-id`)
    expect(res.status()).toBe(404)
  })

  test("workspace upload page renders without crashing", async ({ page }) => {
    const consoleErrors: string[] = []
    page.on("pageerror", err => consoleErrors.push(err.message))
    await page.goto("/workspace/upload")
    await page.waitForLoadState("networkidle")
    expect(consoleErrors).toEqual([])
  })
})
