"use client"

import * as React from "react"
import {
  AlertCircle,
  FileWarning,
  Info,
  CheckCircle2,
  XCircle,
  ChevronDown,
  Lightbulb,
} from "lucide-react"
import { cn } from "@/lib/utils"

export type DefectSeverity = "critical" | "major" | "minor" | "info"

export interface DefectTraceData {
  id: string
  type: string
  severity: DefectSeverity
  message: string
  /** Optional fix the deterministic gate would propose. */
  suggestion?: string
  /** Optional gate name that fired this defect (e.g. "FrequencyGate"). */
  gate?: string
  /** Optional rule id that matched (e.g. "FREQ_BID_ES"). */
  rule?: string
}

export interface ReasoningStep {
  step: string
  status: "pass" | "fail" | "warn"
  details: string
  timestamp?: string
}

export interface DefectTraceProps extends React.HTMLAttributes<HTMLDivElement> {
  defect: DefectTraceData
  /** Per-segment reasoning trace from the multi-agent pipeline. */
  reasoning?: ReasoningStep[]
  /** Render expanded by default. Defaults to false (collapsed). */
  defaultOpen?: boolean
}

const SEVERITY_STYLE: Record<DefectSeverity, { ring: string; bg: string; fg: string; Icon: React.ComponentType<{ size?: number; className?: string }> }> = {
  critical: { ring: "ring-red-300",   bg: "bg-red-50",   fg: "text-red-900",   Icon: AlertCircle  },
  major:    { ring: "ring-amber-300", bg: "bg-amber-50", fg: "text-amber-900", Icon: FileWarning },
  minor:    { ring: "ring-blue-300",  bg: "bg-blue-50",  fg: "text-blue-900",  Icon: Info        },
  info:     { ring: "ring-slate-300", bg: "bg-slate-50", fg: "text-slate-700", Icon: Info        },
}

function StepIcon({ status }: { status: ReasoningStep["status"] }) {
  if (status === "fail") return <XCircle  size={12} className="text-red-500"   aria-label="Fail" />
  if (status === "warn") return <FileWarning size={12} className="text-amber-500" aria-label="Warn" />
  return <CheckCircle2 size={12} className="text-emerald-500" aria-label="Pass" />
}

/**
 * DefectTrace — the rich, expandable counterpart to <DefectChip>.
 *
 * Surfaces the *why* behind a defect: which deterministic gate fired,
 * what rule matched, the suggested fix, and the multi-agent reasoning
 * trace that led to the flag. Built so a reviewer never has to ask
 * "why did the AI think this is wrong" — A2 (quality at gates) made
 * legible.
 */
export function DefectTrace({
  defect,
  reasoning,
  defaultOpen = false,
  className,
  ...rest
}: DefectTraceProps) {
  const [open, setOpen] = React.useState(defaultOpen)
  const style = SEVERITY_STYLE[defect.severity] ?? SEVERITY_STYLE.info
  const Icon = style.Icon

  return (
    <div
      className={cn(
        "rounded-lg border p-3 ring-1",
        style.bg,
        style.fg,
        style.ring,
        className
      )}
      role="region"
      aria-label={`Defect: ${defect.type}`}
      {...rest}
    >
      <div className="flex items-start gap-2">
        <Icon size={14} className="shrink-0 mt-0.5" aria-hidden />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span className="text-sm font-semibold capitalize">
              {defect.type.replace(/_/g, " ")}
            </span>
            <div className="flex items-center gap-2 text-xs opacity-75">
              {defect.gate ? <span>{defect.gate}</span> : null}
              {defect.rule ? <code className="font-mono">{defect.rule}</code> : null}
            </div>
          </div>
          <p className="mt-1 text-sm">{defect.message}</p>
          {defect.suggestion ? (
            <div className="mt-2 flex items-start gap-1.5 text-xs">
              <Lightbulb size={12} className="shrink-0 mt-0.5 opacity-70" aria-hidden />
              <span>
                <span className="font-medium">Suggested:</span> {defect.suggestion}
              </span>
            </div>
          ) : null}

          {reasoning && reasoning.length > 0 ? (
            <button
              type="button"
              onClick={() => setOpen(o => !o)}
              className="mt-2 inline-flex items-center gap-1 text-xs font-medium underline-offset-2 hover:underline"
              aria-expanded={open}
              aria-controls={`defect-${defect.id}-trace`}
            >
              {open ? "Hide reasoning trace" : `Show reasoning trace (${reasoning.length})`}
              <ChevronDown
                size={12}
                className={cn("transition-transform", open && "rotate-180")}
                aria-hidden
              />
            </button>
          ) : null}

          {open && reasoning && reasoning.length > 0 ? (
            <ol
              id={`defect-${defect.id}-trace`}
              className="mt-2 space-y-1.5 border-t border-current/10 pt-2"
            >
              {reasoning.map((s, idx) => (
                <li key={idx} className="flex items-start gap-2 text-xs">
                  <StepIcon status={s.status} />
                  <div className="flex-1 min-w-0">
                    <span className="font-medium">{s.step}</span>
                    <span className="opacity-75"> · {s.details}</span>
                    {s.timestamp ? (
                      <time dateTime={s.timestamp} className="ml-2 opacity-60">
                        {s.timestamp}
                      </time>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          ) : null}
        </div>
      </div>
    </div>
  )
}
