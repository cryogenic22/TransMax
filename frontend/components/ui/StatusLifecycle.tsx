"use client"

import * as React from "react"
import {
  Clock,
  Loader2,
  Sparkles,
  Eye,
  CheckCircle2,
  XCircle,
} from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Six canonical lifecycle states for segments AND jobs in TransMax.
 * Adding a new state means: (1) extend the union, (2) extend STATUS_MAP
 * below, (3) add the matching CSS variables in app/globals.css and the
 * Tailwind utilities in tailwind.config.ts.
 */
export type LifecycleStatus =
  | "pending"
  | "translating"
  | "translated"
  | "reviewed"
  | "approved"
  | "blocked"

const STATUS_MAP: Record<
  LifecycleStatus,
  { label: string; bg: string; fg: string; Icon: React.ComponentType<{ size?: number; className?: string }>; spin?: boolean }
> = {
  pending:     { label: "Pending",     bg: "bg-status-pending-bg",     fg: "text-status-pending-fg",     Icon: Clock },
  translating: { label: "Translating", bg: "bg-status-translating-bg", fg: "text-status-translating-fg", Icon: Loader2, spin: true },
  translated:  { label: "Translated",  bg: "bg-status-translated-bg",  fg: "text-status-translated-fg",  Icon: Sparkles },
  reviewed:    { label: "Reviewed",    bg: "bg-status-reviewed-bg",    fg: "text-status-reviewed-fg",    Icon: Eye },
  approved:    { label: "Approved",    bg: "bg-status-approved-bg",    fg: "text-status-approved-fg",    Icon: CheckCircle2 },
  blocked:     { label: "Blocked",     bg: "bg-status-blocked-bg",     fg: "text-status-blocked-fg",     Icon: XCircle },
}

export interface StatusLifecycleProps
  extends React.HTMLAttributes<HTMLSpanElement> {
  status: LifecycleStatus
  /** Override the displayed label. Defaults to the canonical label. */
  label?: string
}

/**
 * StatusLifecycle — coloured pill with iconography for the 6 canonical
 * states a segment or job moves through. Tokens come from TMX-3601;
 * the icon family stays consistent so a reviewer scanning a list sees
 * status at a glance without reading text.
 */
export function StatusLifecycle({
  status,
  label,
  className,
  ...rest
}: StatusLifecycleProps) {
  const { label: defaultLabel, bg, fg, Icon, spin } = STATUS_MAP[status]
  return (
    <span
      role="status"
      aria-label={`Status: ${label ?? defaultLabel}`}
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        bg,
        fg,
        className
      )}
      {...rest}
    >
      <Icon size={12} className={cn("shrink-0", spin && "animate-spin")} />
      {label ?? defaultLabel}
    </span>
  )
}
