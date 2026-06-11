
import React, { useState } from 'react'
import { CheckCircle2, AlertTriangle, AlertOctagon, BarChart3, Calculator, ChevronDown, ChevronUp, ShieldAlert, HelpCircle } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

// --- Types & Helpers ---

/**
 * TMX-UX-QDASH-REAL: the dashboard renders ONLY data the engine actually
 * produced. Earlier it fabricated accuracy/fluency/terminology bars from the
 * confidence number (a green "98% Accuracy" with no such measurement behind
 * it) — an A3 trust violation on a regulator-facing surface. It now shows the
 * real penalty breakdown + the engine's reasoning, and an honest
 * "scoring unavailable" state when the scorer could not run.
 */
interface PenaltyBreakdown {
    base?: number
    deterministic_penalty?: number
    semantic_penalty?: number
    structural_penalty?: number
    process_penalty?: number
}

interface QualityDashboardProps {
    /** Real confidence 0-100, or null when scoring was unavailable. */
    confidence: number | null
    /** False when the quality scorer could not run for this translation. */
    scoringAvailable: boolean
    /** Engine penalty components (base + per-category penalties). */
    breakdown?: PenaltyBreakdown
    /** Engine's human-readable reasoning lines (the real "why"). */
    breakdownReasoning?: string[]
    sourceText: string
}

const PENALTY_LABELS: Array<{ key: keyof PenaltyBreakdown; label: string }> = [
    { key: 'deterministic_penalty', label: 'QA Defects' },
    { key: 'semantic_penalty', label: 'Semantic Drift' },
    { key: 'structural_penalty', label: 'Structural Risk' },
    { key: 'process_penalty', label: 'Process Gaps' },
]

export function QualityDashboard({ confidence, scoringAvailable, breakdown, breakdownReasoning, sourceText }: QualityDashboardProps) {
    const [isExpanded, setIsExpanded] = useState(false)

    // Detection Logic
    const hasFormulas = /=|[0-9]{2,}/.test(sourceText)
    // Simple PII regex for Email or Basic Phone patterns
    const hasPII = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|(?:\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}/.test(sourceText)

    // RAG Status Logic
    let status: 'green' | 'amber' | 'red' = 'green'
    let statusLabel = 'Ready for Review'
    let StatusIcon: typeof CheckCircle2 = CheckCircle2

    // TMX-UX-QDASH-REAL / A3: a scoring OUTAGE is its own state — never a
    // green verdict and never a red "critical defect" (which would imply we
    // measured a defect). It is amber "scoring unavailable, review required".
    if (!scoringAvailable || confidence === null) {
        status = 'amber'
        statusLabel = 'Quality scoring unavailable — manual review required'
        StatusIcon = HelpCircle
    } else if (confidence < 70) {
        status = 'red'
        statusLabel = 'Critical Issues Detected'
        StatusIcon = AlertOctagon
    } else if (confidence < 90 || hasFormulas || hasPII) {
        status = 'amber'
        statusLabel = 'Human Review Recommended'
        StatusIcon = AlertTriangle
    }

    // Color maps
    const colors = {
        green: { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-900', icon: 'text-emerald-600', bar: 'bg-emerald-500' },
        amber: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-900', icon: 'text-amber-600', bar: 'bg-amber-500' },
        red: { bg: 'bg-rose-50', border: 'border-rose-200', text: 'text-rose-900', icon: 'text-rose-600', bar: 'bg-rose-500' }
    }
    const theme = colors[status]

    return (
        <div className={`rounded-xl border shadow-sm transition-all overflow-hidden mt-6 ${theme.bg} ${theme.border}`}>
            {/* Compact RAG Header (Always Visible) */}
            <div
                onClick={() => setIsExpanded(!isExpanded)}
                className="p-4 flex items-center justify-between cursor-pointer hover:bg-white/40 transition-colors"
                role="button"
            >
                <div className="flex items-center gap-4">
                    <div className={`p-2 rounded-full bg-white shadow-sm ${theme.icon}`}>
                        <StatusIcon size={24} strokeWidth={2.5} />
                    </div>
                    <div>
                        <h3 className={`text-base font-bold ${theme.text}`}>{statusLabel}</h3>
                        <p className="text-xs text-slate-500 font-medium mt-0.5 flex items-center gap-2">
                            AI Confidence: <span className="font-bold text-slate-700">{confidence === null ? 'N/A' : `${confidence.toFixed(1)}%`}</span>
                            {(hasFormulas || hasPII) && (
                                <span className="flex items-center gap-1 text-amber-600 bg-amber-100/50 px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wide font-bold">
                                    Signals Detected
                                </span>
                            )}
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    <div className="text-right hidden sm:block">
                        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Quality Score</span>
                    </div>
                    <button className={`p-1 rounded-md hover:bg-black/5 text-slate-400`}>
                        {isExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                    </button>
                </div>
            </div>

            {/* Expanded Details */}
            <AnimatePresence>
                {isExpanded && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="border-t border-black/5"
                    >
                        <div className="p-6 bg-white/50 space-y-6">

                            {/* TMX-UX-QDASH-REAL: real penalty breakdown + the
                                engine's reasoning. When scoring was unavailable
                                we show an honest note instead of any numbers. */}
                            {!scoringAvailable ? (
                                <div className="flex items-start gap-3 bg-amber-50 p-3 rounded-lg border border-amber-100">
                                    <HelpCircle size={18} className="text-amber-600 mt-0.5 shrink-0" />
                                    <p className="text-sm text-amber-800 leading-snug">
                                        Quality scoring could not run for this translation, so no
                                        confidence score is shown. Treat the output as unverified
                                        and have a qualified reviewer check it before use.
                                    </p>
                                </div>
                            ) : (
                                <div>
                                    <h4 className="text-xs font-bold uppercase text-slate-400 mb-4 tracking-wider flex items-center gap-2">
                                        <BarChart3 size={14} /> Score Breakdown
                                    </h4>
                                    <div className="space-y-1.5 text-sm">
                                        <div className="flex justify-between font-medium text-slate-700">
                                            <span>Base</span>
                                            <span>{breakdown?.base ?? 100}</span>
                                        </div>
                                        {PENALTY_LABELS.map(({ key, label }) => {
                                            const v = breakdown?.[key]
                                            if (!v) return null
                                            return (
                                                <div key={key} className="flex justify-between text-rose-700">
                                                    <span>{label}</span>
                                                    <span>−{v}</span>
                                                </div>
                                            )
                                        })}
                                    </div>
                                    {breakdownReasoning && breakdownReasoning.length > 0 && (
                                        <ul className="mt-4 space-y-1 list-disc list-inside text-xs text-slate-500">
                                            {breakdownReasoning.map((line, i) => (
                                                <li key={i}>{line}</li>
                                            ))}
                                        </ul>
                                    )}
                                </div>
                            )}

                            {/* Warnings / Signals */}
                            {(hasFormulas || hasPII) && (
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                                    {hasFormulas && (
                                        <div className="flex items-start gap-3 bg-amber-50 p-3 rounded-lg border border-amber-100">
                                            <Calculator size={18} className="text-amber-600 mt-0.5 shrink-0" />
                                            <div>
                                                <h5 className="text-xs font-bold text-amber-900 uppercase tracking-wide">Math & Formulas</h5>
                                                <p className="text-sm text-amber-800 mt-1 leading-snug">
                                                    Contains numerical data or equations. Verify unit conversions and formula structure.
                                                </p>
                                            </div>
                                        </div>
                                    )}
                                    {hasPII && (
                                        <div className="flex items-start gap-3 bg-indigo-50 p-3 rounded-lg border border-indigo-100">
                                            <ShieldAlert size={18} className="text-indigo-600 mt-0.5 shrink-0" />
                                            <div>
                                                <h5 className="text-xs font-bold text-indigo-900 uppercase tracking-wide">PII Detected</h5>
                                                <p className="text-sm text-indigo-800 mt-1 leading-snug">
                                                    Potential emails or phone numbers found. Ensure compliance with data privacy policies (GDPR/HIPAA).
                                                </p>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}

                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}

