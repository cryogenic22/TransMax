"use client"

import * as React from "react"
import { ScrollText } from "lucide-react"
import { cn } from "@/lib/utils"
import type { SegmentRevisions } from "@/lib/api"
import { formatRelativeTime } from "@/components/ui/ActivityFeed"

export interface RevisionIndicatorProps
    extends React.HTMLAttributes<HTMLSpanElement> {
    revisions: SegmentRevisions
}

/**
 * RevisionIndicator — TMX-3702-v1.
 *
 * Compact pill rendered next to a segment's status when its source
 * DOCX block carried tracked changes (insertions / deletions / moves).
 * Captured by TMX-3700; surfaced via Segment.element_meta.revisions.
 *
 * v1 is presentation-only: shows that the segment is touched by tracked
 * changes, who, and when. Per-revision accept/reject is TMX-3702-v2.
 *
 * The pill is hidden if all three flags are false (defensive — if the
 * upstream serialiser ever emits an empty revisions object).
 */
export function RevisionIndicator({
    revisions,
    className,
    ...rest
}: RevisionIndicatorProps) {
    const { has_insertions, has_deletions, has_moves, authors, dates } = revisions
    if (!has_insertions && !has_deletions && !has_moves) return null

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
    if (authors.length > 0) titleLines.push(`Authors: ${authors.join(", ")}`)
    if (dates.length > 0) titleLines.push(`Dates: ${dates.join(", ")}`)
    const title = titleLines.join("\n")

    return (
        <span
            role="note"
            aria-label="Segment carries tracked changes"
            className={cn(
                "inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-800",
                className
            )}
            title={title}
            {...rest}
        >
            <ScrollText size={11} className="shrink-0" aria-hidden />
            <span>tracked · {authorLabel}</span>
            {latestDate ? (
                <time dateTime={latestDate} className="opacity-70">
                    · {formatRelativeTime(latestDate)}
                </time>
            ) : null}
        </span>
    )
}
