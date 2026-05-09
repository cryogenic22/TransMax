
import React, { useState } from 'react'
import { CheckCircle2, AlertTriangle, AlertOctagon, BarChart3, Calculator, ChevronDown, ChevronUp, ShieldAlert } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

// --- Types & Helpers ---

interface QualityMetrics {
    accuracy: number
    fluency: number
    terminology: number
    formatting: number
    confidence: number
}

interface QualityDashboardProps {
    metrics: QualityMetrics
    sourceText: string
}

function getStatus(metrics: QualityMetrics, sourceText: string) {
    const hasFormulas = /=|[0-9]{2,}/.test(sourceText)
    const hasPII = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|(?:\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}/.test(sourceText)

    let status: 'green' | 'amber' | 'red' = 'green'
    let label = 'Ready for Review'
    let Icon = CheckCircle2

    if (metrics.confidence < 70) {
        status = 'red'; label = 'Critical Issues'; Icon = AlertOctagon
    } else if (metrics.confidence < 90 || hasFormulas || hasPII) {
        status = 'amber'; label = 'Human Review Needed'; Icon = AlertTriangle
    }

    return { status, label, Icon, hasFormulas, hasPII }
}

const COLORS = {
    green: { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-900', icon: 'text-emerald-600', bar: 'bg-emerald-500', pill: 'bg-emerald-100 text-emerald-800' },
    amber: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-900', icon: 'text-amber-600', bar: 'bg-amber-500', pill: 'bg-amber-100 text-amber-800' },
    red: { bg: 'bg-rose-50', border: 'border-rose-200', text: 'text-rose-900', icon: 'text-rose-600', bar: 'bg-rose-500', pill: 'bg-rose-100 text-rose-800' }
}

// --- Components ---

export function QualitySummaryPill({ metrics, sourceText, onClick, isActive }: QualityDashboardProps & { onClick: () => void, isActive: boolean }) {
    const { status, label, Icon } = getStatus(metrics, sourceText)
    const theme = COLORS[status]

    return (
        <button
            onClick={onClick}
            className={`
                flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wide border transition-all
                ${isActive ? 'ring-2 ring-offset-1 ring-blue-500/30' : 'hover:bg-opacity-80'}
                ${theme.bg} ${theme.border} ${theme.text}
            `}
        >
            <Icon size={14} className={theme.icon} />
            <span>{Math.round(metrics.confidence)}%</span>
            <span className="opacity-50">|</span>
            <span>{label}</span>
            {isActive ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
    )
}

interface QualityDashboardProps {
    metrics: {
        accuracy: number
        fluency: number
        terminology: number
        formatting: number
        confidence: number
    }
    sourceText: string
}

export function QualityDashboard({ metrics, sourceText }: QualityDashboardProps) {
    const [isExpanded, setIsExpanded] = useState(false)

    // Detection Logic
    const hasFormulas = /=|[0-9]{2,}/.test(sourceText)
    // Simple PII regex for Email or Basic Phone patterns
    const hasPII = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|(?:\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}/.test(sourceText)

    // RAG Status Logic
    let status: 'green' | 'amber' | 'red' = 'green'
    let statusLabel = 'Ready for Review'
    let StatusIcon = CheckCircle2

    // Downgrade logic
    if (metrics.confidence < 70) {
        status = 'red'
        statusLabel = 'Critical Issues Detected'
        StatusIcon = AlertOctagon
    } else if (metrics.confidence < 90 || hasFormulas || hasPII) {
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
                            AI Confidence: <span className="font-bold text-slate-700">{metrics.confidence.toFixed(1)}%</span>
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

                            {/* Detailed Scores */}
                            <div>
                                <h4 className="text-xs font-bold uppercase text-slate-400 mb-4 tracking-wider flex items-center gap-2">
                                    <BarChart3 size={14} /> Dimension Breakdown
                                </h4>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                    <ScoreItem label="Accuracy" score={metrics.accuracy} theme={theme} />
                                    <ScoreItem label="Fluency" score={metrics.fluency} theme={theme} />
                                    <ScoreItem label="Terminology" score={metrics.terminology} theme={theme} />
                                    <ScoreItem label="Formatting" score={metrics.formatting} theme={theme} />
                                </div>
                            </div>

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

interface ScoreTheme {
    bar: string
    text: string
    bg: string
}
function ScoreItem({ label, score, theme }: { label: string, score: number, theme: ScoreTheme }) {
    return (
        <div className="p-3 bg-white/80 rounded-lg border border-black/5 shadow-sm">
            <div className="flex justify-between items-end mb-2">
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">{label}</span>
                <span className={`text-sm font-black ${theme.text}`}>{score}%</span>
            </div>
            <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${score}%` }}
                    transition={{ duration: 0.5, ease: "easeOut" }}
                    className={`h-full ${theme.bar} rounded-full`}
                />
            </div>
        </div>
    )
}
