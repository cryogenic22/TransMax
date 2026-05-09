import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { RevisionIndicator } from "@/components/ui/RevisionIndicator"
import type { SegmentRevisions } from "@/lib/api"

const baseRevisions = (overrides: Partial<SegmentRevisions> = {}): SegmentRevisions => ({
    has_insertions: false,
    has_deletions: false,
    has_moves: false,
    authors: [],
    dates: [],
    ...overrides,
})

describe("<RevisionIndicator>", () => {
    it("renders the tracked label when there are insertions", () => {
        render(
            <RevisionIndicator
                revisions={baseRevisions({
                    has_insertions: true,
                    authors: ["Dr. Reviewer"],
                    dates: ["2026-04-01T10:00:00Z"],
                })}
            />
        )
        expect(screen.getByText(/tracked/)).toBeInTheDocument()
        expect(screen.getByText(/Dr\. Reviewer/)).toBeInTheDocument()
    })

    it("renders when there are deletions only", () => {
        render(
            <RevisionIndicator
                revisions={baseRevisions({
                    has_deletions: true,
                    authors: ["Auditor"],
                    dates: ["2026-04-02T11:00:00Z"],
                })}
            />
        )
        expect(screen.getByText(/tracked/)).toBeInTheDocument()
        expect(screen.getByText(/Auditor/)).toBeInTheDocument()
    })

    it("collapses N>1 authors into a count", () => {
        render(
            <RevisionIndicator
                revisions={baseRevisions({
                    has_insertions: true,
                    has_deletions: true,
                    authors: ["A", "B", "C"],
                    dates: ["2026-04-01T10:00:00Z", "2026-04-02T11:00:00Z"],
                })}
            />
        )
        expect(screen.getByText(/3 authors/)).toBeInTheDocument()
    })

    it("returns null when all flags are false (defensive guard)", () => {
        const { container } = render(
            <RevisionIndicator
                revisions={baseRevisions({
                    authors: ["A"],
                    dates: ["2026-04-01T10:00:00Z"],
                })}
            />
        )
        expect(container.firstChild).toBeNull()
    })

    it("attaches a multi-line tooltip with full author + date list", () => {
        const { container } = render(
            <RevisionIndicator
                revisions={baseRevisions({
                    has_insertions: true,
                    has_moves: true,
                    authors: ["A", "B"],
                    dates: ["2026-04-01T10:00:00Z", "2026-04-02T11:00:00Z"],
                })}
            />
        )
        const span = container.querySelector("span[role='note']")
        const title = span?.getAttribute("title") ?? ""
        expect(title).toContain("Has insertions")
        expect(title).toContain("Has moves")
        expect(title).toContain("Authors: A, B")
        expect(title).toContain("Dates: 2026-04-01")
    })

    it("uses the role='note' aria semantics", () => {
        render(
            <RevisionIndicator
                revisions={baseRevisions({ has_insertions: true, authors: ["A"], dates: ["2026-04-01T10:00:00Z"] })}
            />
        )
        expect(screen.getByRole("note", { name: /tracked changes/i })).toBeInTheDocument()
    })
})
