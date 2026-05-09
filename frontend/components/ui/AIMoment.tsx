"use client"

import * as React from "react"
import { Sparkles, ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"

export interface AIMomentProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Provider + model identifier. e.g. "Claude Sonnet 4.6", "GPT-4o". */
  model: string
  /** Versioned prompt id from app/agents/prompts/. e.g. "translator-v1.0.0". */
  promptVersion?: string
  /** Token usage for this generation, surfaced for cost transparency. */
  tokensIn?: number
  tokensOut?: number
  /** ISO-8601 UTC timestamp of when the artefact was generated. */
  generatedAt?: string
  /**
   * Optional explanation. When provided, the header shows a chevron toggle
   * that reveals this text inline. Keep it terse — one paragraph max.
   */
  explanation?: string
  /** The AI-generated artefact itself (translation, defect note, etc.). */
  children: React.ReactNode
}

/**
 * AIMoment — wraps any AI-generated artefact in TransMax's signature
 * "this is AI" treatment: violet→cyan gradient strip, sparkle, model
 * chip, and an optional collapsible explanation. Tokens come from
 * TMX-3601.
 *
 * Reuse target: every translation output, every defect explanation,
 * every suggested fix, every generated narrative. If AI made it, it
 * lives in an AIMoment.
 */
export function AIMoment({
  model,
  promptVersion,
  tokensIn,
  tokensOut,
  generatedAt,
  explanation,
  children,
  className,
  ...rest
}: AIMomentProps) {
  const [open, setOpen] = React.useState(false)
  const tokens =
    tokensIn !== undefined && tokensOut !== undefined
      ? `${tokensIn} in · ${tokensOut} out`
      : null

  return (
    <div
      className={cn(
        "rounded-lg border border-ai-border bg-ai-tint overflow-hidden",
        className
      )}
      role="region"
      aria-label="AI-generated content"
      {...rest}
    >
      {/* Signature gradient strip — the across-the-platform "this is AI" cue */}
      <div className="h-1 bg-ai-gradient" aria-hidden />

      <div className="flex items-center justify-between gap-3 px-3 py-2 text-xs">
        <div className="flex items-center gap-2 min-w-0">
          <Sparkles
            className="shrink-0 text-ai-spark"
            size={14}
            aria-hidden
          />
          <span className="font-medium text-foreground/80 truncate">
            AI · {model}
          </span>
          {promptVersion ? (
            <span className="text-muted-foreground/80 truncate">
              · {promptVersion}
            </span>
          ) : null}
        </div>
        {explanation ? (
          <button
            type="button"
            onClick={() => setOpen(o => !o)}
            className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors"
            aria-expanded={open}
            aria-controls="ai-moment-explanation"
          >
            How
            <ChevronDown
              size={12}
              className={cn("transition-transform", open && "rotate-180")}
              aria-hidden
            />
          </button>
        ) : null}
      </div>

      {/* Body — the AI artefact */}
      <div className="px-3 pb-3">{children}</div>

      {/* Footer — explanation + token usage + timestamp.
          Always visible (when info is present); the explanation expands
          on toggle. Cost transparency is non-negotiable for A6 (LLMs as
          qualified suppliers). */}
      {(explanation || tokens || generatedAt) && (
        <div className="border-t border-ai-border/60 bg-background/40 px-3 py-2 text-xs text-muted-foreground space-y-1">
          {explanation && open ? (
            <p
              id="ai-moment-explanation"
              className="text-foreground/80 leading-relaxed"
            >
              {explanation}
            </p>
          ) : null}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            {tokens ? <span>{tokens}</span> : null}
            {generatedAt ? <time dateTime={generatedAt}>{generatedAt}</time> : null}
          </div>
        </div>
      )}
    </div>
  )
}
