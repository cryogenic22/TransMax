import { test, expect, type Route } from "@playwright/test"

// TMX-3709 — a11y regression coverage for the three app modals.
// Pre-fix, each was an inline-styled div overlay with no role,
// no focus trap, no Escape handler. Section 508 hard fail for
// keyboard and screen-reader users.

// ── Stubs reused across modals ─────────────────────────────────────────

const STUB_DOC_ID = "stub-modal-a11y"

const STUB_DOC_LIST = {
  items: [
    {
      id: STUB_DOC_ID,
      name: "modal-a11y-fixture.docx",
      file_type: "docx",
      status: "translated",
      source_language: "en",
      target_language: "de",
      glossary_id: null,
      segment_count: 4,
      word_count: 80,
      page_count: 1,
      confidence_score: 0.92,
      total_tokens: 320,
      total_cost_usd: 0.0042,
      created_at: "2026-05-09T20:00:00Z",
      updated_at: "2026-05-09T20:30:00Z",
    },
  ],
  total: 1,
  page: 1,
  page_size: 20,
}

// ── JobsView delete-confirm modal ───────────────────────────────────────

test.describe("Modal a11y — JobsView delete-confirm (TMX-3709)", () => {
  test("opens, has dialog role + aria-modal, Escape closes", async ({ page }) => {
    await page.route("**/api/**", async (route: Route) => {
      const url = route.request().url()
      const method = route.request().method()
      if (
        method === "GET" &&
        url.includes("/api/documents") &&
        !url.includes(`/api/documents/${STUB_DOC_ID}`)
      ) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(STUB_DOC_LIST),
        })
        return
      }
      if (method === "GET" && url.endsWith(`/api/documents/${STUB_DOC_ID}/segments`)) {
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

    await page.goto("/workspace/control?tab=jobs")
    await page.waitForLoadState("networkidle")

    // Open the modal via the trash icon.
    const trigger = page.locator('[title="Delete document"]').first()
    await trigger.click()

    // Dialog must have role=dialog + aria-modal=true (radix sets both).
    const dialog = page.getByRole("dialog")
    await expect(dialog).toBeVisible()
    await expect(dialog).toHaveAttribute("aria-modal", "true")
    // The dialog must be programmatically labelled by its heading.
    await expect(dialog).toHaveAccessibleName(/delete document/i)

    // Focus is inside the dialog (radix auto-focuses the first focusable
    // child or the dialog itself). Active element should be inside the
    // dialog node.
    const focusInsideDialog = await dialog.evaluate(
      (el) => el.contains(document.activeElement)
    )
    expect(focusInsideDialog).toBe(true)

    // Pressing Escape closes the dialog.
    await page.keyboard.press("Escape")
    await expect(dialog).toBeHidden()
  })
})

// ── Tools-page Black Book correction modal ──────────────────────────────

test.describe("Modal a11y — Black Book correction modal (TMX-3709)", () => {
  test("opens, has dialog role + aria-modal, Escape closes", async ({ page }) => {
    await page.route("**/api/**", async (route: Route) => {
      const url = route.request().url()
      const method = route.request().method()
      if (
        method === "POST" &&
        url.endsWith("/api/tools/translate/universal")
      ) {
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
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({}),
      })
    })

    await page.goto("/workspace")
    await page.waitForLoadState("networkidle")

    // Translate first so FeedbackControls renders.
    await page.locator("textarea").first().fill("Take twice daily.")
    await page.locator("button:has-text('Translate')").first().click()
    await page.waitForLoadState("networkidle")

    // Open the correction modal via 👎.
    await page.locator('button[title="Report issue"]').click()

    const dialog = page.getByRole("dialog")
    await expect(dialog).toBeVisible()
    await expect(dialog).toHaveAttribute("aria-modal", "true")
    await expect(dialog).toHaveAccessibleName(/submit correction/i)

    const focusInsideDialog = await dialog.evaluate(
      (el) => el.contains(document.activeElement)
    )
    expect(focusInsideDialog).toBe(true)

    await page.keyboard.press("Escape")
    await expect(dialog).toBeHidden()
  })
})

// ── Upload-page translation estimate modal ──────────────────────────────

test.describe("Modal a11y — upload estimate dialog (TMX-3709)", () => {
  test("opens, has dialog role + aria-modal, Escape closes", async ({ page }) => {
    await page.route("**/api/**", async (route: Route) => {
      const url = route.request().url()
      const method = route.request().method()
      // Successful upload returns a document.
      if (method === "POST" && url.endsWith("/api/documents")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: STUB_DOC_ID,
            name: "stub.txt",
            file_type: "txt",
            status: "uploaded",
            source_language: "en",
            target_language: "de",
            glossary_id: null,
            segment_count: 1,
            word_count: 4,
            page_count: 1,
            confidence_score: null,
            total_tokens: 0,
            total_cost_usd: 0,
            created_at: "2026-05-12T00:00:00Z",
            updated_at: "2026-05-12T00:00:00Z",
          }),
        })
        return
      }
      // Segments fetch after upload.
      if (
        method === "GET" &&
        url.endsWith(`/api/documents/${STUB_DOC_ID}/segments`)
      ) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              id: "seg-1",
              document_id: STUB_DOC_ID,
              order_index: 1,
              source_text: "Take twice daily.",
              translated_text: null,
              confidence_score: null,
              status: "pending",
              gate_results: {},
              validation_score: null,
              reverse_translation: null,
              element_meta: null,
              created_at: "2026-05-12T00:00:00Z",
              updated_at: "2026-05-12T00:00:00Z",
            },
          ]),
        })
        return
      }
      // Estimate endpoint.
      if (
        method === "GET" &&
        url.includes(`/api/documents/${STUB_DOC_ID}/estimate`)
      ) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            total_llm_calls: 1,
            estimated_total_tokens: 50,
            estimated_cost_usd: 0.0005,
            estimated_seconds: 3,
            model: "gpt-4o-mini",
            segment_count: 1,
            word_count: 4,
          }),
        })
        return
      }
      // Glossaries.
      if (url.includes("/api/knowledge/glossaries")) {
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

    await page.goto("/workspace/upload")
    await page.waitForLoadState("networkidle")

    // Upload a file via the hidden input.
    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: "stub.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Take twice daily."),
    })

    // Wait for the upload to land segments.
    await expect(page.getByText(/stub\.txt/)).toBeVisible({ timeout: 15000 })

    // Click "Translate" — opens the estimate confirmation dialog.
    await page.getByRole("button", { name: /^translate$/i }).first().click()

    const dialog = page.getByRole("dialog")
    await expect(dialog).toBeVisible({ timeout: 10000 })
    await expect(dialog).toHaveAttribute("aria-modal", "true")
    await expect(dialog).toHaveAccessibleName(/translation estimate/i)

    const focusInsideDialog = await dialog.evaluate(
      (el) => el.contains(document.activeElement)
    )
    expect(focusInsideDialog).toBe(true)

    await page.keyboard.press("Escape")
    await expect(dialog).toBeHidden()
  })
})
