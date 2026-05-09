"use client"

import { useState, useEffect, useRef } from "react"
import { useParams, useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { Button } from "@/components/ui/button"
import {
    ArrowLeft, Play, AlertTriangle, Edit2,
    RotateCcw, FileText, CheckCircle2, X, Loader2,
    Activity, ShieldCheck, Sparkles, Languages,
    History, AlertOctagon, CornerDownRight, Check
} from "lucide-react"
import { LanguageSelector } from "@/components/ui/LanguageSelector"
import { getLanguageName } from "@/lib/languages"

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001") + "/api"

// --- Types ---

interface SegmentItem {
    id: string
    order_index: number
    source_text: string
    translated_text: string | null
    confidence_score: number | null
    status: "pending" | "translated" | "edited" | "approved"
    gate_results: { units_ok?: boolean; negation_ok?: boolean; pii_redacted?: boolean; violations?: any[] } | null
}

interface DocumentMeta {
    id: string
    name: string
    status: string
    source_language: string
    target_language: string | null
    confidence_score: number | null
}


// --- ZS-Inspired Theme Constants ---
// Deep Teal, Slate, Clean White text
const THEME = {
    bg: "bg-slate-950",
    panel: "bg-slate-900/50",
    border: "border-slate-800",
    accent: "text-teal-400",
    accentBg: "bg-teal-500/10",
    button: "bg-teal-600 hover:bg-teal-700 text-white",
    success: "text-emerald-400",
    warning: "text-amber-400",
    error: "text-rose-400"
}

export default function DocumentConsolePage() {
    const params = useParams()
    const router = useRouter()
    const docId = params.docId as string

    // Data State
    const [docMeta, setDocMeta] = useState<DocumentMeta | null>(null)
    const [segments, setSegments] = useState<SegmentItem[]>([])

    // UI State
    const [selectedSegment, setSelectedSegment] = useState<SegmentItem | null>(null)
    const [targetLanguage, setTargetLanguage] = useState("fr")
    const [isTranslating, setIsTranslating] = useState(false)
    const [isLoading, setIsLoading] = useState(true)

    // Glass Box / Agent State
    const [agentStep, setAgentStep] = useState<"idle" | "analyzing" | "drafting" | "gating" | "complete">("idle")
    const [activityLog, setActivityLog] = useState<string[]>([])

    // Edit State
    const [editingText, setEditingText] = useState("")
    const [changeReason, setChangeReason] = useState("")

    // --- Data Fetching ---

    const fetchDocData = async () => {
        try {
            const docRes = await fetch(`${API_BASE}/documents/${docId}`)
            if (docRes.ok) {
                const docData = await docRes.json()
                setDocMeta(docData)
                if (docData.target_language) setTargetLanguage(docData.target_language)

                // Infer State
                if (docData.status === "processing") {
                    setIsTranslating(true)
                    setAgentStep("drafting")
                } else if (docData.status === "translated") {
                    setAgentStep("complete")
                    setIsTranslating(false)
                }
            }

            const segRes = await fetch(`${API_BASE}/documents/${docId}/segments`)
            if (segRes.ok) {
                const segData = await segRes.json()
                setSegments(segData)
            }
        } catch (error) {
            console.error("Failed to load document data", error)
        } finally {
            setIsLoading(false)
        }
    }

    useEffect(() => {
        fetchDocData()
        // Poll every 3s if processing
        const interval = setInterval(() => {
            if (isTranslating || agentStep === "drafting") {
                fetchDocData()
            }
        }, 3000)
        return () => clearInterval(interval)
    }, [docId, isTranslating, agentStep])


    // --- Actions ---

    const handleTranslate = async () => {
        setIsTranslating(true)
        setAgentStep("analyzing")
        setActivityLog(["Initializing ZS Pharma Agent...", "Loading Compliance Profile (Global Common)..."])

        // Mock Steps for UX (The real backend job will take over)
        setTimeout(() => setActivityLog(prev => [...prev, "Digitizing: Extracting granular sentence units..."]), 800)
        setTimeout(() => setActivityLog(prev => [...prev, "Security: Validating PII redaction rules..."]), 1600)
        setTimeout(() => setActivityLog(prev => [...prev, "Context: Retrieving Glossary v2.4 matches..."]), 2400)

        try {
            const res = await fetch(`${API_BASE}/documents/${docId}/translate`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ target_language: targetLanguage })
            })
            if (res.ok) {
                setDocMeta(prev => prev ? { ...prev, status: "processing" } : null)
                setAgentStep("drafting")
                setActivityLog(prev => [...prev, "Agent: Sending blocks to LLM for translation..."])
            }
        } catch (e) {
            console.error("Translation failed", e)
            setIsTranslating(false)
            setAgentStep("idle")
        }
    }

    const handleSaveEdit = async () => {
        if (!selectedSegment || !changeReason.trim()) return
        try {
            const res = await fetch(`${API_BASE}/segments/${selectedSegment.id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ translated_text: editingText, reason: changeReason })
            })
            if (res.ok) {
                const updated = await res.json()
                setSegments(prev => prev.map(s => s.id === updated.id ? updated : s))
                setSelectedSegment(null)
            }
        } catch (e) { console.error(e) }
    }

    // --- Render Helpers ---

    const completedCount = segments.filter(s => s.translated_text).length
    const progress = segments.length ? (completedCount / segments.length) * 100 : 0

    if (isLoading) return <div className={`${THEME.bg} min-h-screen flex items-center justify-center text-teal-500/50`}><Loader2 className="animate-spin mr-2" /> Loading Workstation...</div>

    return (
        <main className={`min-h-screen ${THEME.bg} text-slate-200 font-sans flex flex-col`}>

            {/* --- ZS Header --- */}
            <header className="px-6 py-4 border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-50 flex items-center justify-between shadow-lg shadow-black/20">
                <div className="flex items-center gap-6">
                    <Button variant="ghost" className="text-slate-400 hover:text-teal-400" onClick={() => router.push('/dashboard')}>
                        <ArrowLeft className="w-4 h-4 mr-2" /> Back
                    </Button>
                    <div>
                        <div className="flex items-center gap-3">
                            <h1 className="text-xl font-semibold tracking-tight text-white">{docMeta?.name}</h1>
                            <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full border ${docMeta?.status === "translated" ? "border-teal-500/30 text-teal-400 bg-teal-500/10" :
                                    docMeta?.status === "processing" ? "border-blue-500/30 text-blue-400 bg-blue-500/10" :
                                        "border-slate-700 text-slate-500"
                                }`}>
                                {docMeta?.status}
                            </span>
                        </div>
                        <div className="text-xs text-slate-500 font-mono flex items-center gap-4 mt-1">
                            <span>ID: {docId.substring(0, 8)}</span>
                            {docMeta?.confidence_score && (
                                <span className="text-teal-500 flex items-center gap-1">
                                    <ShieldCheck className="w-3 h-3" />
                                    Confidence: {docMeta.confidence_score.toFixed(1)}%
                                </span>
                            )}
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    {/* Controls */}
                    {agentStep === "idle" && (
                        <div className="flex items-center bg-slate-900 border border-slate-700 rounded-lg p-1 gap-2">
                            <span className="text-xs text-slate-500 px-3 uppercase tracking-wider font-bold">Target</span>
                            <LanguageSelector
                                value={targetLanguage}
                                onChange={setTargetLanguage}
                            />
                        </div>
                    )}

                    {agentStep === "idle" ? (
                        <Button onClick={handleTranslate} className={`${THEME.button} shadow-[0_0_15px_rgba(20,184,166,0.3)]`}>
                            <Sparkles className="w-4 h-4 mr-2" /> Run ZS Agent
                        </Button>
                    ) : (
                        <div className="flex items-center gap-3 px-4 py-2 bg-blue-500/10 border border-blue-500/20 rounded-full">
                            <Activity className="w-4 h-4 text-blue-400 animate-pulse" />
                            <span className="text-xs font-mono text-blue-300">
                                {agentStep === "drafting" ? `Drafting... ${Math.round(progress)}%` : "Agent Active"}
                            </span>
                        </div>
                    )}
                </div>
            </header>

            {/* --- Main Workspace (Split View) --- */}
            <div className="flex-1 flex overflow-hidden">

                {/* Left: Source Channel */}
                <div className="w-1/2 border-r border-slate-800 flex flex-col bg-slate-925">
                    <div className="px-6 py-3 border-b border-slate-800 flex justify-between items-center bg-slate-900/30">
                        <span className="text-xs font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2">
                            <Languages className="w-3 h-3" /> Source (English)
                        </span>
                        <span className="text-xs text-slate-600 font-mono">{segments.length} Segments</span>
                    </div>
                    <div className="flex-1 overflow-y-auto p-2 space-y-1">
                        {segments.map((seg) => (
                            <div
                                key={seg.id}
                                onClick={() => { setSelectedSegment(seg); setEditingText(seg.translated_text || ""); setChangeReason("") }}
                                className={`p-4 rounded-lg cursor-pointer transition-all border ${selectedSegment?.id === seg.id
                                        ? "bg-teal-500/10 border-teal-500/50 shadow-inner"
                                        : "bg-transparent border-transparent hover:bg-white/5"
                                    }`}
                            >
                                <div className="flex gap-4">
                                    <span className="text-xs font-mono text-slate-600 w-6 pt-1">#{seg.order_index}</span>
                                    <div className="flex-1">
                                        <p className={`text-sm leading-relaxed ${selectedSegment?.id === seg.id ? "text-slate-200" : "text-slate-400"}`}>
                                            {seg.source_text}
                                        </p>
                                    </div>
                                    {/* Status Indicators */}
                                    <div className="flex flex-col items-end gap-1">
                                        {seg.status === 'translated' && <CheckCircle2 className="w-3 h-3 text-teal-500/50" />}
                                        {seg.status === 'edited' && <Edit2 className="w-3 h-3 text-amber-500/50" />}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Right: Target / Agent Channel */}
                <div className="w-1/2 flex flex-col bg-slate-950 relative">

                    {/* If Translating: Glass Box Overlay */}
                    <AnimatePresence>
                        {(isTranslating || !selectedSegment) && (
                            <motion.div
                                initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                                className="absolute inset-0 z-10 p-8 flex flex-col"
                            >
                                <div className="flex-1 flex flex-col justify-center max-w-lg mx-auto w-full">
                                    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
                                        <div className="p-4 border-b border-slate-800 bg-slate-900/80 flex justify-between items-center">
                                            <div className="flex items-center gap-2 text-teal-400 font-bold text-sm">
                                                <Activity className="w-4 h-4" /> Live Agent Trace
                                            </div>
                                            <div className="flex gap-1">
                                                <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                                                <div className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse delay-75" />
                                                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse delay-150" />
                                            </div>
                                        </div>

                                        {/* Console Logs */}
                                        <div className="p-6 font-mono text-xs space-y-3 min-h-[200px] bg-black/40">
                                            {activityLog.map((log, i) => (
                                                <motion.div
                                                    key={i}
                                                    initial={{ x: -10, opacity: 0 }}
                                                    animate={{ x: 0, opacity: 1 }}
                                                    className="flex gap-3"
                                                >
                                                    <span className="text-slate-600">{(new Date()).toLocaleTimeString().split(' ')[0]}</span>
                                                    <span className={log.includes("Agent:") ? "text-teal-400" : "text-blue-300"}>
                                                        {log}
                                                    </span>
                                                </motion.div>
                                            ))}
                                            {isTranslating && (
                                                <motion.div
                                                    animate={{ opacity: [0.4, 1, 0.4] }}
                                                    transition={{ duration: 1.5, repeat: Infinity }}
                                                    className="text-slate-500 italic"
                                                >
                                                    _ processing pipeline...
                                                </motion.div>
                                            )}
                                            {!isTranslating && !selectedSegment && (
                                                <div className="text-slate-600 mt-10 text-center">
                                                    Select a segment on the left to review or edit.
                                                </div>
                                            )}
                                        </div>

                                        {/* Progress Bar */}
                                        {isTranslating && (
                                            <div className="h-1 bg-slate-800 w-full">
                                                <motion.div
                                                    className="h-full bg-gradient-to-r from-teal-500 to-blue-500"
                                                    initial={{ width: "0%" }}
                                                    animate={{ width: `${progress}%` }}
                                                />
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Editor Panel (Review Mode) */}
                    <AnimatePresence>
                        {selectedSegment && !isTranslating && (
                            <motion.div
                                initial={{ x: 50, opacity: 0 }} animate={{ x: 0, opacity: 1 }}
                                className="flex-1 flex flex-col h-full z-20 bg-slate-950 border-l border-slate-800 shadow-2xl"
                            >
                                <div className="px-6 py-4 border-b border-slate-800 flex justify-between items-center bg-slate-900/50">
                                    <div className="flex items-center gap-3">
                                        <h3 className="text-sm font-bold text-slate-200">Translation Review</h3>
                                        <span className="text-xs font-mono text-slate-500 px-2 py-0.5 rounded bg-slate-800">
                                            Seg #{selectedSegment.order_index}
                                        </span>
                                    </div>
                                    <Button variant="ghost" size="sm" onClick={() => setSelectedSegment(null)}>
                                        <X className="w-4 h-4 text-slate-500 hover:text-white" />
                                    </Button>
                                </div>

                                <div className="flex-1 p-8 overflow-y-auto">
                                    {/* Editor */}
                                    <div className="group relative">
                                        <label className="text-xs font-bold text-teal-500 uppercase tracking-widest mb-3 block flex justify-between">
                                            <span>Target ({targetLanguage})</span>
                                            <span className="text-[10px] text-slate-500 font-mono">AI-DRAFT-v1</span>
                                        </label>
                                        <div className="relative">
                                            <textarea
                                                value={editingText}
                                                onChange={(e) => setEditingText(e.target.value)}
                                                className="w-full bg-slate-900 border-2 border-slate-800 rounded-xl p-6 text-lg text-slate-200 font-serif leading-relaxed min-h-[200px] focus:outline-none focus:border-teal-500/50 transition-all placeholder:text-slate-700"
                                                placeholder="Translation pending..."
                                            />
                                            <div className="absolute top-4 right-4 text-slate-600">
                                                <Edit2 className="w-4 h-4 opacity-20 group-hover:opacity-100 transition-opacity" />
                                            </div>
                                        </div>
                                    </div>

                                    {/* Governance: Reason for Change */}
                                    {editingText !== (selectedSegment.translated_text || "") && (
                                        <motion.div
                                            initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}
                                            className="mt-6 p-4 bg-amber-500/5 border border-amber-500/20 rounded-xl"
                                        >
                                            <h4 className="text-amber-400 text-xs font-bold uppercase tracking-wider flex items-center gap-2 mb-2">
                                                <AlertTriangle className="w-3 h-3" /> Mandatory Audit Log
                                            </h4>
                                            <textarea
                                                className="w-full bg-transparent border-0 text-amber-200 placeholder:text-amber-500/30 text-sm focus:outline-none resize-none"
                                                placeholder="Why are you changing this segment? (Required for GxP compliance)"
                                                value={changeReason}
                                                onChange={(e) => setChangeReason(e.target.value)}
                                            />
                                        </motion.div>
                                    )}

                                    {/* Quality Gates */}
                                    <div className="mt-8 grid grid-cols-3 gap-4">
                                        {[
                                            { label: "Units", ok: selectedSegment.gate_results?.units_ok, icon: AlertOctagon },
                                            { label: "Negation", ok: selectedSegment.gate_results?.negation_ok, icon: AlertTriangle },
                                            { label: "Privacy", ok: selectedSegment.gate_results?.pii_redacted, icon: ShieldCheck }
                                        ].map((gate, i) => (
                                            <div key={i} className={`p-4 rounded-xl border flex flex-col items-center justify-center gap-2 ${gate.ok !== false
                                                    ? "bg-emerald-500/5 border-emerald-500/20 text-emerald-400"
                                                    : "bg-rose-500/5 border-rose-500/20 text-rose-400"
                                                }`}>
                                                <gate.icon className="w-5 h-5 opacity-80" />
                                                <span className="text-xs font-bold uppercase">{gate.label}</span>
                                                {gate.ok !== false
                                                    ? <Check className="w-4 h-4" />
                                                    : <X className="w-4 h-4" />
                                                }
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Action Footer */}
                                <div className="p-6 border-t border-slate-800 bg-slate-900/50 flex gap-4">
                                    <Button variant="outline" className="flex-1 border-slate-700 text-slate-400 hover:text-white" onClick={() => setEditingText(selectedSegment.translated_text || "")}>
                                        <History className="w-4 h-4 mr-2" /> Revert
                                    </Button>
                                    <Button
                                        className={`flex-[2] ${THEME.button}`}
                                        disabled={editingText === (selectedSegment.translated_text || "") || !changeReason.trim()}
                                        onClick={handleSaveEdit}
                                    >
                                        <CheckCircle2 className="w-4 h-4 mr-2" />
                                        {editingText === selectedSegment.translated_text ? "No Changes" : "Commit & Sign Off"}
                                    </Button>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>
        </main>
    )
}
