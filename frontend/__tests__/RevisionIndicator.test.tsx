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

    // ── TMX-3702-counts: per-type revision count display ─────────────

    it("shows '· N changes' when total count is at least 2", () => {
        render(
            <RevisionIndicator
                revisions={baseRevisions({
                    has_insertions: true,
                    has_deletions: true,
                    n_insertions: 3,
                    n_deletions: 2,
                    authors: ["Dr. Reviewer"],
                    dates: ["2026-04-01T10:00:00Z"],
                })}
            />
        )
        // 3 + 2 = 5 changes; reviewer-facing language is "changes" not "marks"
        expect(screen.getByText(/5 changes/)).toBeInTheDocument()
    })

    it("hides the changes count when total is exactly 1 (avoids cluttering single-edit pills)", () => {
        render(
            <RevisionIndicator
                revisions={baseRevisions({
                    has_insertions: true,
                    n_insertions: 1,
                    n_deletions: 0,
                    n_moves_from: 0,
                    n_moves_to: 0,
                    authors: ["A"],
                    dates: ["2026-04-01T10:00:00Z"],
                })}
            />
        )
        expect(screen.queryByText(/changes/)).not.toBeInTheDocument()
    })

    it("hides the changes count when count fields are absent (back-compat with older payload)", () => {
        // Older backend payloads don't include n_* keys at all.
        render(
            <RevisionIndicator
                revisions={baseRevisions({
                    has_insertions: true,
                    authors: ["A"],
                    dates: ["2026-04-01T10:00:00Z"],
                })}
            />
        )
        expect(screen.queryByText(/changes/)).not.toBeInTheDocument()
    })

    it("uses the role='note' aria semantics", () => {
        render(
            <RevisionIndicator
                revisions={baseRevisions({ has_insertions: true, authors: ["A"], dates: ["2026-04-01T10:00:00Z"] })}
            />
        )
        // /tracked change/i matches both singular ("Tracked change by A")
        // and plural ("5 tracked changes by …") accessible names — the
        // dynamic label change in TMX-3702-a11y picks one based on count.
        expect(screen.getByRole("note", { name: /tracked change/i })).toBeInTheDocument()
    })

    // ── TMX-3702-a11y: dynamic accessible-name carries direction + count ─

    it("a11y: moveFrom-only fixture's accessible name says 'moved out of this segment'", () => {
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
        // The accessible name (aria-label) must carry direction so screen
        // readers don't collapse "moved out" / "moved in" / "tracked" into
        // one generic phrase.
        expect(
            screen.getByRole("note", { name: /moved out of this segment/i })
        ).toBeInTheDocument()
        // And it must NOT say "tracked changes" — that would mislead SR
        // users into thinking the segment has insertions/deletions.
        expect(
            screen.queryByRole("note", { name: /tracked changes/i })
        ).not.toBeInTheDocument()
    })

    it("a11y: moveTo-only fixture's accessible name says 'moved into this segment'", () => {
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
        expect(
            screen.getByRole("note", { name: /moved into this segment/i })
        ).toBeInTheDocument()
    })

    it("a11y: high-count fixture's accessible name surfaces magnitude", () => {
        render(
            <RevisionIndicator
                revisions={baseRevisions({
                    has_insertions: true,
                    has_deletions: true,
                    n_insertions: 12,
                    n_deletions: 8,
                    authors: ["Senior", "QC", "Reg"],
                    dates: ["2026-04-01T10:00:00Z"],
                })}
            />
        )
        // 20 changes by 3 authors — the SR user should hear the count
        // (otherwise they only get the binary "tracked" cue).
        expect(
            screen.getByRole("note", { name: /20 tracked changes by 3 authors/i })
        ).toBeInTheDocument()
    })

    it("a11y: back-compat — no n_* fields → singular 'Tracked change' with no bogus count", () => {
        render(
            <RevisionIndicator
                revisions={baseRevisions({
                    has_insertions: true,
                    authors: ["A"],
                    dates: ["2026-04-01T10:00:00Z"],
                })}
            />
        )
        // Older payloads omit n_* — accessible name must NOT say
        // "0 tracked changes" or "NaN changes". Singular "Tracked change".
        const note = screen.getByRole("note", { name: /tracked change by A/i })
        expect(note).toBeInTheDocument()
        expect(note.getAttribute("aria-label")).not.toMatch(/\d+ tracked/i)
        expect(note.getAttribute("aria-label")).not.toMatch(/NaN/i)
    })
})
