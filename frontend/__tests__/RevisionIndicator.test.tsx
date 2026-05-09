import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { RevisionIndicator } from "@/components/ui/RevisionIndicator"
import type { SegmentRevisions } from "@/lib/api"

const baseRevisions = (overrides: Partial<SegmentRevisions> = {}): SegmentRevisions => ({
    has_insertions: false,
    has_deletions: false,
    has_moves: false,
    has_moves_from: false,
    has_moves_to: false,
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

    // ── TMX-3704-ui: directional move semantics ─────────────────────

    it("renders 'moved out' when only has_moves_from is true", () => {
        render(
            <RevisionIndicator
                revisions={baseRevisions({
                    has_moves: true,
                    has_moves_from: true,
                    has_moves_to: false,
                    authors: ["Mover"],
                    dates: ["2026-04-03T12:00:00Z"],
                })}
            />
        )
        expect(screen.getByText(/moved out/)).toBeInTheDocument()
        expect(screen.queryByText(/^tracked/)).not.toBeInTheDocument()
    })

    it("renders 'moved in' when only has_moves_to is true", () => {
        render(
            <RevisionIndicator
                revisions={baseRevisions({
                    has_moves: true,
                    has_moves_from: false,
                    has_moves_to: true,
                    authors: ["Mover"],
                    dates: ["2026-04-03T12:00:00Z"],
                })}
            />
        )
        expect(screen.getByText(/moved in/)).toBeInTheDocument()
    })

    it("renders 'moved' when both directions are true", () => {
        render(
            <RevisionIndicator
                revisions={baseRevisions({
                    has_moves: true,
                    has_moves_from: true,
                    has_moves_to: true,
                    authors: ["Mover"],
                    dates: ["2026-04-03T12:00:00Z"],
                })}
            />
        )
        const moved = screen.getByText(/moved/)
        // Plain "moved" — not "moved out" / "moved in"
        expect(moved.textContent).not.toMatch(/moved (in|out)/)
    })

    it("falls back to 'tracked' when moves combine with insertions/deletions", () => {
        render(
            <RevisionIndicator
                revisions={baseRevisions({
                    has_insertions: true,
                    has_moves: true,
                    has_moves_from: true,
                    authors: ["A"],
                    dates: ["2026-04-01T10:00:00Z"],
                })}
            />
        )
        expect(screen.getByText(/tracked/)).toBeInTheDocument()
    })

    it("title tooltip includes directional move info when present", () => {
        const { container } = render(
            <RevisionIndicator
                revisions={baseRevisions({
                    has_moves: true,
                    has_moves_from: true,
                    has_moves_to: false,
                    authors: ["Mover"],
                    dates: ["2026-04-03T12:00:00Z"],
                })}
            />
        )
        const title = container.querySelector("span[role='note']")?.getAttribute("title") ?? ""
        expect(title).toContain("moves from")
        expect(title).not.toContain("moves to")
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
