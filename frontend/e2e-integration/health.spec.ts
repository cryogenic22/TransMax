import { test, expect } from "@playwright/test"

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8001"

test.describe("Backend health (live integration)", () => {
  test("GET /health returns 200 with the expected JSON shape", async ({
    request,
  }) => {
    const res = await request.get(`${BACKEND}/health`)
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toMatchObject({
      status: "ok",
      service: expect.any(String),
      version: expect.any(String),
    })
  })

  test("GET /api/dashboard/stats returns 200 with stat fields", async ({
    request,
  }) => {
    const res = await request.get(`${BACKEND}/api/dashboard/stats`)
    expect(res.status()).toBe(200)
    const body = await res.json()
    // The shape may evolve, but each call must succeed and return an object.
    expect(typeof body).toBe("object")
    expect(body).not.toBeNull()
  })

  test("CORS allows the frontend origin", async ({ request }) => {
    const res = await request.fetch(`${BACKEND}/api/dashboard/stats`, {
      method: "OPTIONS",
      headers: {
        Origin: "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
      },
    })
    // FastAPI's CORS middleware should respond to the preflight successfully.
    expect([200, 204]).toContain(res.status())
    const allowOrigin = res.headers()["access-control-allow-origin"]
    // Either explicit echo of the origin or a wildcard suffices.
    expect(allowOrigin === "http://localhost:3000" || allowOrigin === "*").toBe(true)
  })
})
