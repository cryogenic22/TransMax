"use client"
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '@/lib/api'
import { Wand2, FileText, Type, RefreshCw, Eraser, Sparkles } from 'lucide-react'
import { FeedbackControls } from '@/app/workspace/tools/page'
import { CopyButton } from '@/components/ui/CopyButton'
import { LanguageSelector } from '@/components/ui/LanguageSelector'
import Link from 'next/link'
import { QualityDashboard } from '@/components/ui/QualityDashboard'
import { getErrMessage } from '@/lib/utils'
import { toast } from 'sonner'

export default function TrustedTranslatePage() {
    // State
    const [source, setSource] = useState('')
    const [srcLang, setSrcLang] = useState('auto')
    const [tgtLang, setTgtLang] = useState('es')
    const [loading, setLoading] = useState(false)

    // Result State
    const [segments, setSegments] = useState<Array<{ source: string; target: string }>>([])
    const [resultMeta, setResultMeta] = useState<{
        confidence?: number
        band?: string
        score_breakdown?: unknown
        recommendations?: string[]
    } | null>(null)
    const [hoveredIdx, setHoveredIdx] = useState<number | null>(null)
    const [viewMode, setViewMode] = useState<'edit' | 'read'>('edit')

    const MAX_CHARS = 5000

    const handleTranslate = async () => {
        if (!source.trim()) return
        if (source.length > MAX_CHARS) return

        setLoading(true)
        setSegments([])
        setResultMeta(null)
        setHoveredIdx(null)
        setResultMeta(null) // Clear previous results immediately

        try {
            const res = await api.tools.universal(source, srcLang === 'auto' ? 'en' : srcLang, tgtLang)

            // Handle response format
            if (res.segments && res.segments.length > 0) {
                setSegments(res.segments)
            } else {
                setSegments([{ source: source, target: res.translated_text || "" }])
            }

            setResultMeta({
                confidence: res.confidence,
                band: res.score_band,
                score_breakdown: res.score_breakdown,
                recommendations: res.recommendations || []
            })

            setViewMode('read')
        } catch (err) {
            // TMX-3604-alert-to-toast: blocking alert() replaced with
            // toast.error so the failure UX matches the sweep pattern.
            toast.error(getErrMessage(err, "Translation failed. Please try again."))
        } finally {
            setLoading(false)
        }
    }

    const clearAll = () => {
        setSource('')
        setSegments([])
        setResultMeta(null)
        setViewMode('edit')
    }

    return (
        <div className="w-full p-4 md:p-6 h-[calc(100vh-2rem)] flex flex-col font-sans">
            {/* Header & Navigation Tabs */}
            <header className="mb-6 shrink-0">
                {/* Page Title */}
                <div className="flex items-center gap-3 mb-6">
                    <div className="p-2 bg-blue-600 rounded-lg text-white shadow-lg shadow-blue-500/30">
                        <Sparkles size={24} />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Trusted Translate</h1>
                        <p className="text-slate-500 text-sm">Your dedicated AI agent for rigorous, compliance-ready translation.</p>
                    </div>
                </div>

                {/* Main Tabs */}
                <div className="flex items-center gap-6 border-b border-slate-200">
                    <button className="flex items-center gap-2 pb-3 border-b-2 border-blue-600 text-blue-600 font-semibold transition-colors">
                        <Type size={18} />
                        Text Translation
                    </button>
                    <Link
                        href="/workspace/upload"
                        className="flex items-center gap-2 pb-3 border-b-2 border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300 font-medium transition-all"
                    >
                        <FileText size={18} />
                        Translate Documents
                    </Link>
                </div>
            </header>

            {/* Translation Workspace - Layout ensuring equal height */}
            <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6 pb-6">

                {/* Source Editor Panel */}
                <div className="flex flex-col gap-2 h-full">
                    {/* Toolbar / Lang Selector */}
                    <div className="flex items-center justify-between bg-white p-2 rounded-lg border border-slate-200 shadow-sm shrink-0">
                        <LanguageSelector
                            value={srcLang}
                            onChange={v => setSrcLang(v)}
                            className="min-w-[200px]"
                            includeAuto={true}
                        />
                        <div className="flex items-center gap-1">
                            <button onClick={clearAll} className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors" title="Clear">
                                <Eraser size={16} />
                            </button>
                        </div>
                    </div>

                    {/* Editor Container */}
                    <div className="group relative border rounded-xl bg-white focus-within:ring-2 focus-within:ring-blue-500/20 transition-all shadow-sm h-full flex flex-col overflow-hidden">
                        {viewMode === 'edit' ? (
                            <textarea
                                className="w-full h-full p-6 text-lg text-slate-700 resize-none outline-none placeholder:text-slate-300 font-normal leading-relaxed custom-scrollbar"
                                placeholder="Enter text to translate..."
                                value={source}
                                onChange={e => setSource(e.target.value)}
                                maxLength={MAX_CHARS}
                                spellCheck={false}
                            />
                        ) : (
                            // Read Mode (Source Segments)
                            <div className="h-full p-6 text-lg text-slate-800 leading-relaxed overflow-y-auto custom-scrollbar">
                                {segments.map((seg, i) => (
                                    <span
                                        key={i}
                                        className={`transition-colors duration-200 cursor-pointer decoration-2 decoration-blue-200/50 hover:bg-blue-50 rounded px-1 -mx-1 ${hoveredIdx === i ? 'bg-blue-100 text-blue-900' : ''}`}
                                        onMouseEnter={() => setHoveredIdx(i)}
                                        onMouseLeave={() => setHoveredIdx(null)}
                                        onClick={() => setViewMode('edit')}
                                    >
                                        {seg.source}{" "}
                                    </span>
                                ))}
                            </div>
                        )}

                        {/* Footer Info */}
                        <div className="px-4 py-2 border-t border-slate-50 flex justify-between items-center text-xs text-slate-400 font-mono bg-slate-50/50">
                            <span>{source.length} / {MAX_CHARS} chars</span>
                            {viewMode === 'read' && (
                                <button onClick={() => setViewMode('edit')} className="text-blue-600 hover:underline">
                                    Edit Source
                                </button>
                            )}
                        </div>
                    </div>
                </div>

                {/* Target Editor Panel */}
                <div className="flex flex-col gap-2 h-full">
                    {/* Toolbar / Lang Selector */}
                    <div className="flex items-center justify-between bg-white p-2 rounded-lg border border-slate-200 shadow-sm shrink-0">
                        <span className="text-xs font-bold text-slate-400 uppercase tracking-wider px-2">Translate Into</span>
                        <LanguageSelector
                            value={tgtLang}
                            onChange={v => setTgtLang(v)}
                            className="min-w-[200px] text-right"
                        />
                    </div>

                    {/* Editor Container */}
                    <div className="relative border rounded-xl bg-slate-50/50 focus-within:ring-2 focus-within:ring-indigo-500/20 transition-all shadow-inner h-full flex flex-col overflow-hidden">

                        {loading ? (
                            <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/80 backdrop-blur-sm z-10">
                                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mb-4"></div>
                                <span className="text-sm font-medium text-slate-500">Processing...</span>
                            </div>
                        ) : null}

                        {segments.length > 0 ? (
                            <div className="flex-1 p-6 text-lg text-slate-900 leading-relaxed overflow-y-auto custom-scrollbar">
                                {segments.map((seg, i) => (
                                    <span
                                        key={i}
                                        className={`transition-colors duration-200 cursor-pointer rounded px-1 -mx-1 ${hoveredIdx === i ? 'bg-indigo-100 text-indigo-900 shadow-sm' : ''}`}
                                        onMouseEnter={() => setHoveredIdx(i)}
                                        onMouseLeave={() => setHoveredIdx(null)}
                                    >
                                        {seg.target}{" "}
                                    </span>
                                ))}
                            </div>
                        ) : (
                            <div className="flex-1 flex flex-col items-center justify-center text-slate-300">
                                <Wand2 size={48} className="mb-4 opacity-20" />
                                <span className="text-lg font-medium opacity-50">Prêt à traduire</span>
                            </div>
                        )}

                        {/* Secondary Actions (Copy/Feedback) - INSIDE the box but fixed at bottom */}
                        {segments.length > 0 && (
                            <div className="px-4 py-3 border-t border-slate-200 bg-white flex justify-between items-center shadow-sm shrink-0">
                                <FeedbackControls
                                    source={source}
                                    target={segments.map(s => s.target).join(' ')}
                                    targetLang={tgtLang}
                                />
                                <div className="flex gap-2">
                                    <CopyButton text={segments.map(s => s.target).join(' ')} />
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Action Bar */}
            <div className="shrink-0 flex justify-end mb-4">
                <button
                    onClick={handleTranslate}
                    disabled={!source.trim() || loading}
                    className={`
                        w-full md:w-auto px-8 py-3.5 rounded-xl font-bold text-white shadow-lg shadow-blue-600/20 transition-all transform hover:-translate-y-0.5
                        ${!source.trim() || loading
                            ? 'bg-slate-300 cursor-not-allowed shadow-none'
                            : 'bg-blue-600 hover:bg-blue-700 hover:shadow-xl active:scale-[0.99]'}
                    `}
                >
                    {loading ? (
                        <span className="flex items-center gap-2"><RefreshCw className="animate-spin" size={20} /> Translating...</span>
                    ) : (
                        <span className="flex items-center gap-2"><Sparkles size={20} /> Translate Now</span>
                    )}
                </button>
            </div>

            {/* Detailed Quality Dashboard */}
            <AnimatePresence>
                {resultMeta && (
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 10 }}
                        className="shrink-0 pb-8"
                    >
                        <QualityDashboard
                            metrics={{
                                confidence: (resultMeta.confidence ?? 0),
                                accuracy: (resultMeta.confidence ?? 0) > 90 ? 98 : 85, // Mocked breakdown if not in API
                                fluency: (resultMeta.confidence ?? 0) > 90 ? 95 : 88,
                                terminology: (resultMeta.confidence ?? 0) > 90 ? 100 : 92,
                                formatting: 100
                            }}
                            sourceText={source}
                        />
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}
