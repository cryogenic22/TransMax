"use client"

import * as React from "react"
import { CheckCircle2, Loader2, XCircle } from "lucide-react"
import { cn } from "@/lib/utils"

export type AgentId = "translator" | "reviewer" | "fixer" | "auditor"
export type ActivityStatus = "in_progress" | "complete" | "failed"

export interface AgentActivity {
  id: string
  agent: AgentId
  label: string
  startedAt: string
  durationMs?: number
  status: ActivityStatus
}

const AGENT_META: Record<
  AgentId,
  { label: string; cssVar: string }
> = {
  translator: { label: "Translator", cssVar: "var(--agent-translator)" },
  reviewer:   { label: "Reviewer",   cssVar: "var(--agent-reviewer)"   },
  fixer:      { label: "Fixer",      cssVar: "var(--agent-fixer)"      },
  auditor:    { label: "Auditor",    cssVar: "var(--agent-auditor)"    },
}

const AGENT_ORDER: AgentId[] = ["translator", "reviewer", "fixer", "auditor"]

function formatDuration(ms?: number): string | null {
  if (ms === undefined) return null
  if (ms < 1000) return `${ms}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.round(ms / 60_000)}m`
}

function StatusIcon({ status }: { status: ActivityStatus }) {
  if (status === "in_progress") return <Loader2 size={11} className="animate-spin" aria-label="In progress" />
  if (status === "failed")      return <XCircle  size={11} aria-label="Failed" />
  return <CheckCircle2 size={11} aria-label="Complete" />
}

export interface AgentLanesProps extends React.HTMLAttributes<HTMLDivElement> {
  activities: AgentActivity[]
}

/**
 * AgentLanes — multi-agent swim-lane visualisation.
 *
 * One lane per agent (translator, reviewer, fixer, auditor). Each activity
 * renders as a chip on its lane with start time, duration, and status.
 * Reads at a glance: a reviewer sees four entities at work, not a generic
 * progress bar.
 *
 * Backend wiring (TMX-3603-wire) populates `activities` from OTel spans +
 * audit events. This component is presentation-only.
 */
export function AgentLanes({
  activities,
  className,
  ...rest
}: AgentLanesProps) {
  const byAgent = React.useMemo(() => {
    const grouped: Record<AgentId, AgentActivity[]> = {
      translator: [],
      reviewer: [],
      fixer: [],
      auditor: [],
    }
    for (const a of activities) grouped[a.agent].push(a)
    return grouped
  }, [activities])

  if (activities.length === 0) {
    return (
      <div
        className={cn(
          "rounded-lg border bg-card px-4 py-6 text-center text-sm text-muted-foreground",
          className
        )}
        {...rest}
      >
        No agent activity yet.
      </div>
    )
  }

  return (
    <div
      className={cn("space-y-2 rounded-lg border bg-card p-3", className)}
      role="region"
      aria-label="Agent activity"
      {...rest}
    >
      {AGENT_ORDER.map(agent => {
        const items = byAgent[agent]
        const meta = AGENT_META[agent]
        return (
          <div
            key={agent}
            className="flex items-center gap-3"
            data-agent={agent}
          >
            <div
              className="w-20 shrink-0 text-xs font-medium"
              style={{ color: meta.cssVar }}
            >
              {meta.label}
            </div>
            <div className="flex flex-1 flex-wrap items-center gap-1.5 min-h-[1.5rem]">
              {items.length === 0 ? (
                <span className="text-xs text-muted-foreground/60">—</span>
              ) : (
                items.map(act => (
                  <span
                    key={act.id}
                    className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs"
                    style={{
                      borderColor: meta.cssVar,
                      color: meta.cssVar,
                      backgroundColor: `color-mix(in srgb, ${meta.cssVar} 10%, transparent)`,
                    }}
                    title={`${act.label} — started ${act.startedAt}`}
                  >
                    <StatusIcon status={act.status} />
                    <span className="truncate max-w-[10rem]">{act.label}</span>
                    {formatDuration(act.durationMs) ? (
                      <span className="opacity-70">· {formatDuration(act.durationMs)}</span>
                    ) : null}
                  </span>
                ))
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
