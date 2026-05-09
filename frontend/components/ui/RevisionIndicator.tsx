"use client"

import * as React from "react"
import { ScrollText, ArrowLeft, ArrowRight, ArrowLeftRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { totalRevisionCount, type SegmentRevisions } from "@/lib/api"
import { formatRelativeTime } from "@/components/ui/ActivityFeed"

export interface RevisionIndicatorProps
    extends React.HTMLAttributes<HTMLSpanElement> {
    revisions: SegmentRevisions
}

type IconType = React.ComponentType<{ size?: number; className?: string; "aria-hidden"?: boolean }>

/**
 * Decide the headline label + icon for a revision set. Insertions or
 * deletions present (with or without moves) win the "tracked" path so
 * the editorial change is the visible cue. Pure move-only segments get
 * a directional label per TMX-3704-ui.
 */
function chooseHeadline(revisions: SegmentRevisions): { label: string; Icon: IconType } {
    const { has_insertions, has_deletions, has_moves_from, has_moves_to } = revisions
    if (has_insertions || has_deletions) {
        return { label: "tracked", Icon: ScrollText }
    }
    // Pure moves — pick the directional variant.
    if (has_moves_from && has_moves_to) return { label: "moved", Icon: ArrowLeftRight }
    if (has_moves_from) return { label: "moved out", Icon: ArrowRight }
    if (has_moves_to) return { label: "moved in", Icon: ArrowLeft }
    // Fallback (shouldn't reach here if the caller checked has_moves correctly).
    return { label: "tracked", Icon: ScrollText }
}

/**
 * TMX-3702-a11y: build a descriptive aria-label that distinguishes
 * direction (moved out vs moved in vs both) and surfaces magnitude
 * (count of changes, count of authors). Visible text is deliberately
 * terse — this is the screen-reader counterpart that's allowed to be
 * a complete sentence.
 */
export function accessibleRevisionLabel(revisions: SegmentRevisions): string {
    const { has_insertions, has_deletions, has_moves_from, has_moves_to, authors } = revisions
    const total = totalRevisionCount(revisions)
    const byClause =
        authors.length === 0
            ? ""
            : authors.length === 1
                ? ` by ${authors[0]}`
                : ` by ${authors.length} authors`

    if (has_insertions || has_deletions) {
        if (total >= 2) return `${total} tracked changes${byClause}`
        return `Tracked change${byClause}`
    }
    if (has_moves_from && has_moves_to) return `Text moved within this segment${byClause}`
    if (has_moves_from) return `Text moved out of this segment${byClause}`
    if (has_moves_to) return `Text moved into this segment${byClause}`
    // Defensive — caller already returned null when no flags are set, but
    // keep a sensible fallback so the SR user still gets context.
    return `Segment carries tracked changes`
}

/**
 * RevisionIndicator — TMX-3702-v1 / TMX-3704-ui.
 *
 * Compact pill rendered next to a segment's status when its source
 * DOCX block carried tracked changes (insertions / deletions / moves).
 * Captured by TMX-3700; surfaced via Segment.element_meta.revisions.
 *
 * Headline label:
 *   - "tracked" with ScrollText when there are insertions or deletions
 *     (with or without moves) — editorial change wins the eye.
 *   - "moved out" / ArrowRight when only `has_moves_from`.
 *   - "moved in"  / ArrowLeft  when only `has_moves_to`.
 *   - "moved"    / ArrowLeftRight when both directions.
 *
 * v1 is presentation-only: shows that the segment is touched by tracked
 * changes, who, and when. Per-revision accept/reject is TMX-3702-v2
 * (ADR-0004, awaiting approval).
 *
 * The pill is hidden if no flags are set (defensive — if the upstream
 * serialiser ever emits an empty revisions object).
 */
export function RevisionIndicator({
    revisions,
    className,
    ...rest
}: RevisionIndicatorProps) {
    const { has_insertions, has_deletions, has_moves, has_moves_from, has_moves_to, authors, dates } = revisions
    if (!has_insertions && !has_deletions && !has_moves) return null

    const { label, Icon } = chooseHeadline(revisions)

    const authorLabel =
        authors.length === 0
            ? "—"
            : authors.length === 1
                ? authors[0]
                : `${authors.length} authors`

    // Latest date wins for the headline; full chronology in the tooltip.
    const latestDate = dates.length > 0 ? dates[dates.length - 1] : null

    const titleLines: string[] = []
    if (has_insertions) titleLines.push("Has insertions")
    if (has_deletions) titleLines.push("Has deletions")
    if (has_moves) titleLines.push("Has moves")
    if (has_moves_from) titleLines.push("Has moves from (text relocated away)")
    if (has_moves_to) titleLines.push("Has moves to (text arrived here)")
    if (authors.length > 0) titleLines.push(`Authors: ${authors.join(", ")}`)
    if (dates.length > 0) titleLines.push(`Dates: ${dates.join(", ")}`)
    const title = titleLines.join("\n")

    return (
        <span
            role="note"
            aria-label={accessibleRevisionLabel(revisions)}
            className={cn(
                "inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-800",
                className
            )}
            title={title}
            {...rest}
        >
            <Icon size={11} className="shrink-0" aria-hidden />
            <span>{label}</span>
            {/* TMX-3702-counts: surface count when total ≥ 2 — single-edit
                pills stay clean since "1 change" is redundant with "tracked". */}
            {totalRevisionCount(revisions) >= 2 ? (
                <span className="opacity-70">· {totalRevisionCount(revisions)} changes</span>
            ) : null}
            <span>· {authorLabel}</span>
            {latestDate ? (
                <time dateTime={latestDate} className="opacity-70">
                    · {formatRelativeTime(latestDate)}
                </time>
            ) : null}
        </span>
    )
}
