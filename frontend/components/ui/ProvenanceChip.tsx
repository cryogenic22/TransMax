"use client"

import * as React from "react"
import { Fingerprint } from "lucide-react"
import { cn } from "@/lib/utils"

export interface ProvenanceChipProps
  extends React.HTMLAttributes<HTMLSpanElement> {
  /** The originating agent / pipeline / human. e.g. "translator agent". */
  source: string
  /** Optional version qualifier. e.g. "prompt v1.0.0", "rev 4". */
  version?: string
  /** ISO-8601 UTC timestamp of when this provenance was recorded. */
  timestamp?: string
  /**
   * Cryptographic hash that anchors this content in the audit chain.
   * Rendered in monospace inside the hover-tooltip; never truncated in
   * the tooltip so the user can copy the full hash.
   */
  hash?: string
}

/**
 * ProvenanceChip — a small chip near any content block that surfaces
 * its source, version, timestamp, and audit hash. The hash makes
 * audit-by-default (A1) visible, not just stored in the DB.
 *
 * Reuse target: every segment row, every audit event, every search
 * result, every review action.
 */
export function ProvenanceChip({
  source,
  version,
  timestamp,
  hash,
  className,
  ...rest
}: ProvenanceChipProps) {
  const tooltip = [
    `Source: ${source}`,
    version ? `Version: ${version}` : null,
    timestamp ? `Recorded: ${timestamp}` : null,
    hash ? `Hash: ${hash}` : null,
  ]
    .filter(Boolean)
    .join("\n")

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-audit-chip-border bg-audit-chip px-2 py-0.5 text-xs text-audit-chip-fg",
        className
      )}
      title={tooltip}
      {...rest}
    >
      {hash ? (
        <Fingerprint className="shrink-0" size={11} aria-hidden />
      ) : null}
      <span className="truncate max-w-[16rem]">{source}</span>
      {version ? (
        <span className="text-audit-chip-fg/70">· {version}</span>
      ) : null}
      {hash ? (
        <code className="text-audit-hash font-mono text-[10px]">
          · {hash.length > 10 ? `${hash.slice(0, 8)}…` : hash}
        </code>
      ) : null}
    </span>
  )
}
