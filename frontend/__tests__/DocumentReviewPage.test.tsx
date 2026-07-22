import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import type { Document, Segment } from "@/lib/api"

// TMX-SCORECARD-MOCK (A3): the document-review Quality Scorecard must never
// show invented quality figures. Three failure modes are pinned here:
//  1. the hardcoded mock initial state (overall_score: 94, "Negation Safety"
//     88) must not exist in the source at all — it is one refactor away from
//     painting in front of a reviewer;
//  2. while the fetch is pending, the page shows its honest loading state,
//     never scorecard numbers;
//  3. when the quality engine never scored the document (no gate_results on
//     any segment), the page must say "scoring unavailable" — NOT a
//     fabricated 100 / "All Checks Passed" (vacuous green).

const documentsGet = vi.fn<(id: string) => Promise<Document>>()
const segmentsList = vi.fn<(docId: string) => Promise<Segment[]>>()

vi.mock("@/lib/api", async (importOriginal) => {
  // Keep the real module (types/helpers) but stub the network surface.
  const mod = await importOriginal<typeof import("@/lib/api")>()
  return {
    ...mod,
    api: {
      documents: { get: (id: string) => documentsGet(id) },
      segments: { list: (docId: string) => segmentsList(docId) },
    },
  }
})
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "doc-1" }) }))
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }))

import DocumentReviewPage from "@/app/workspace/documents/[id]/page"

// Vitest runs with cwd = frontend/ (the config root).
const PAGE_SOURCE_PATH = resolve(
  process.cwd(),
  "app/workspace/documents/[id]/page.tsx"
)

const doc: Document = {
  id: "doc-1",
  name: "protocol.docx",
  file_type: "docx",
  status: "translated",
  source_language: "en",
  target_language: "de",
  created_at: "2026-07-22T00:00:00Z",
  updated_at: "2026-07-22T00:00:00Z",
}

function makeSegment(overrides: Partial<Segment>): Segment {
  return {
    id: "seg-1",
    document_id: "doc-1",
    order_index: 0,
    source_text: "Do not exceed the stated dose.",
    translated_text: "Die angegebene Dosis nicht überschreiten.",
    status: "translated",
    confidence_score: null,
    validation_score: null,
    reverse_translation: null,
    created_at: "2026-07-22T00:00:00Z",
    updated_at: "2026-07-22T00:00:00Z",
    ...overrides,
  }
}

beforeEach(() => {
  documentsGet.mockReset()
  segmentsList.mockReset()
})

describe("DocumentReviewPage — no fabricated quality scorecard (A3)", () => {
  it("contains no mock scorecard literals in the page source", () => {
    const source = readFileSync(PAGE_SOURCE_PATH, "utf-8")
    expect(source).not.toMatch(/overall_score:\s*94/)
    expect(source).not.toMatch(/score:\s*88/)
    expect(source).not.toMatch(/score:\s*96/)
    expect(source).not.toMatch(/Mock scorecard/i)
  })

  it("shows the honest loading state — never scorecard numbers — while the fetch is pending", () => {
    // Unresolved promises: the reviewer is looking at first paint.
    documentsGet.mockReturnValue(new Promise<Document>(() => undefined))
    segmentsList.mockReturnValue(new Promise<Segment[]>(() => undefined))

    render(<DocumentReviewPage />)

    expect(screen.getByText("Loading document...")).toBeInTheDocument()
    // The old mock's invented figures must not be in the DOM.
    expect(screen.queryByText("94")).not.toBeInTheDocument()
    expect(screen.queryByText("Negation Safety")).not.toBeInTheDocument()
    expect(screen.queryByText("88%")).not.toBeInTheDocument()
    expect(screen.queryByText("Quality Score")).not.toBeInTheDocument()
  })

  it("renders the honest 'scoring unavailable' state — not a fabricated perfect score — when no segment has gate results", async () => {
    documentsGet.mockResolvedValue(doc)
    // Quality engine never ran: no gate_results on any segment.
    segmentsList.mockResolvedValue([
      makeSegment({ id: "seg-1", order_index: 0 }),
      makeSegment({ id: "seg-2", order_index: 1 }),
    ])

    render(<DocumentReviewPage />)

    expect(
      await screen.findByText(/quality scoring unavailable/i)
    ).toBeInTheDocument()
    // The vacuous-green verdict must be gone: no invented 100, no green
    // "All Checks Passed", no per-category percentages.
    expect(screen.queryByText("All Checks Passed")).not.toBeInTheDocument()
    expect(screen.queryByText("Quality Score")).not.toBeInTheDocument()
    expect(screen.queryByText("100")).not.toBeInTheDocument()
    expect(screen.queryByText("100%")).not.toBeInTheDocument()
  })

  it("still renders the real computed scorecard when segments carry gate results", async () => {
    documentsGet.mockResolvedValue(doc)
    segmentsList.mockResolvedValue([
      makeSegment({
        id: "seg-1",
        order_index: 0,
        gate_results: {
          violations: [
            {
              category: "negation_error",
              severity: "critical",
              message: "Negation dropped in target.",
            },
          ],
        },
      }),
      makeSegment({ id: "seg-2", order_index: 1, gate_results: { violations: [] } }),
    ])

    render(<DocumentReviewPage />)

    // 1 of 2 segments has a critical violation → overall 50, BLOCKED,
    // Negation Safety 100 - 15 = 85 with 1 issue.
    expect(await screen.findByText("Critical Issues Found")).toBeInTheDocument()
    expect(screen.getByText("50")).toBeInTheDocument()
    expect(screen.getByText("Negation Safety")).toBeInTheDocument()
    expect(screen.getByText("85%")).toBeInTheDocument()
    expect(
      screen.queryByText(/quality scoring unavailable/i)
    ).not.toBeInTheDocument()
  })
})
