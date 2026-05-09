import * as React from "react"
import { cn } from "@/lib/utils"

interface ConfidenceMeterProps {
    score: number
    breakdown?: {
        base?: number
        deterministic_penalty?: number
        semantic_penalty?: number
        structural_penalty?: number
        process_penalty?: number
    }
    reasoning?: string[]
    className?: string
}

export function ConfidenceMeter({ score, breakdown, reasoning, className }: ConfidenceMeterProps) {
    // 0-100 score
    // >= 95: Very High (Green)
    // >= 80: High (Teal)
    // >= 60: Medium (Amber)
    // < 60: Low (Red)

    let colorClass = "text-red-600 bg-red-100 border-red-200"
    if (score >= 95) colorClass = "text-emerald-700 bg-emerald-100 border-emerald-200"
    else if (score >= 80) colorClass = "text-teal-700 bg-teal-100 border-teal-200"
    else if (score >= 60) colorClass = "text-amber-700 bg-amber-100 border-amber-200"

    return (
        <div className={cn("group relative inline-block cursor-help", className)}>
            <div className={cn(
                "flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-sm font-semibold transition-all",
                colorClass
            )}>
                <span className="text-xs uppercase opacity-70">Trust</span>
                <span>{score.toFixed(0)}</span>
            </div>

            {/* Tooltip / Popover (Simple CSS group-hover for now) */}
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-slate-900/95 text-slate-50 text-xs rounded-lg shadow-xl opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50 backdrop-blur-sm">
                <div className="font-semibold mb-2 pb-1 border-b border-white/10 flex justify-between">
                    <span>Score Breakdown</span>
                    <span className="text-emerald-400">100 Base</span>
                </div>

                <div className="space-y-1.5">
                    {/* Only show non-zero penalties */}
                    {breakdown?.deterministic_penalty ? (
                        <div className="flex justify-between text-red-300">
                            <span>QA Defects</span>
                            <span>-{breakdown.deterministic_penalty}</span>
                        </div>
                    ) : null}
                    {breakdown?.semantic_penalty ? (
                        <div className="flex justify-between text-amber-300">
                            <span>Semantic Drift</span>
                            <span>-{breakdown.semantic_penalty}</span>
                        </div>
                    ) : null}
                    {breakdown?.structural_penalty ? (
                        <div className="flex justify-between text-orange-300">
                            <span>Structural Risk</span>
                            <span>-{breakdown.structural_penalty}</span>
                        </div>
                    ) : null}

                    {(!breakdown?.deterministic_penalty && !breakdown?.semantic_penalty && !breakdown?.structural_penalty && score < 100) && (
                        <div className="italic opacity-70">Calculated penalty...</div>
                    )}

                    {score === 100 && (
                        <div className="text-emerald-400 flex items-center gap-1">
                            ✓ No risks detected
                        </div>
                    )}
                </div>

                {reasoning && reasoning.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-white/10 text-[10px] opacity-80 space-y-1">
                        {reasoning.slice(0, 3).map((r, i) => (
                            <div key={i}>• {r}</div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    )
}
