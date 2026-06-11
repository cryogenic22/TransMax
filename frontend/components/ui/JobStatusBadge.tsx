import * as React from "react"
import { CheckCircle2, Play, Clock, AlertCircle } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * TMX-UX-STATUS-DRY: the single source of truth for a TRANSLATION JOB's status
 * badge (queued | processing | completed | failed). It replaces two duplicated
 * `getStatusBadge` helpers — one of which hard-coded hex colours — in
 * `app/workspace/jobs/page.tsx` and `components/control_views/JobsView.tsx`.
 *
 * Distinct from `<StatusBadge>` (the document/segment LIFECYCLE vocab:
 * APPROVED / BLOCKED / REVIEW_REQUIRED …) on purpose — two different status
 * domains, one component each, rather than one component branching on both.
 */
const JOB_STATUS_STYLES: Record<string, { classes: string; Icon: typeof Clock }> = {
    completed: { classes: "bg-green-100 text-green-800 border-green-200", Icon: CheckCircle2 },
    processing: { classes: "bg-blue-100 text-blue-800 border-blue-200", Icon: Play },
    queued: { classes: "bg-slate-100 text-slate-600 border-slate-200", Icon: Clock },
    failed: { classes: "bg-red-100 text-red-700 border-red-200", Icon: AlertCircle },
}

export function JobStatusBadge({ status, className }: { status: string; className?: string }) {
    const style = JOB_STATUS_STYLES[status] ?? JOB_STATUS_STYLES.queued
    const Icon = style.Icon
    const label = status.charAt(0).toUpperCase() + status.slice(1)
    return (
        <span
            className={cn(
                "inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border",
                style.classes,
                className
            )}
        >
            <Icon size={14} /> {label}
        </span>
    )
}
