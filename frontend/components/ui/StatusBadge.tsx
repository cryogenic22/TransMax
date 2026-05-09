import * as React from "react"
import { cn } from "@/lib/utils"

type StatusType = "APPROVED" | "COMPLETED" | "REJECTED" | "BLOCKED" | "REVIEW_REQUIRED" | "PENDING" | "PROCESSING"

interface StatusBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
    status: string
}

export function StatusBadge({ status, className, ...props }: StatusBadgeProps) {
    const normalized = status.toUpperCase() as StatusType

    let colorClass = "bg-slate-100 text-slate-800 border-slate-200" // Default/Pending

    if (["APPROVED", "COMPLETED"].includes(normalized)) {
        colorClass = "bg-green-100 text-green-800 border-green-200 dark:bg-green-900/30 dark:text-green-300 dark:border-green-800"
    } else if (["REJECTED", "BLOCKED"].includes(normalized)) {
        colorClass = "bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800"
    } else if (["REVIEW_REQUIRED", "PROCESSING"].includes(normalized)) {
        colorClass = "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-800"
    }

    return (
        <span
            className={cn(
                "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border",
                colorClass,
                className
            )}
            {...props}
        >
            {status}
        </span>
    )
}
