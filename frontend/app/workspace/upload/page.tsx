"use client"

import { useState, useCallback, useRef, useEffect } from "react"
import {
    Upload, FileText, Languages, CheckCircle2, Download,
    ArrowLeft, Loader2, AlertCircle, X, ArrowLeftRight,
    RotateCcw, ExternalLink
} from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { api, Document, Segment } from "@/lib/api"
import { BookOpen } from "lucide-react"
import { LanguageSelector } from "@/components/ui/LanguageSelector"
import { getLanguageName } from "@/lib/languages"
import { getErrMessage } from "@/lib/utils"
import { LiveIsland, AgentStep } from "@/components/ui/live-island"
import { toast } from "sonner"
import { addActiveJob, removeActiveJob } from "@/hooks/useTranslationNotifications"

type FlowState = "idle" | "uploaded" | "translating" | "done" | "estimating"

export default function TranslateDocumentPage() {
    const router = useRouter()
    const [state, setState] = useState<FlowState>("idle")
    const [document, setDocument] = useState<Document | null>(null)
    const [segments, setSegments] = useState<Segment[]>([])
    const [sourceLanguage, setSourceLanguage] = useState("auto")
    const [targetLanguage, setTargetLanguage] = useState("de")
    const [isUploading, setIsUploading] = useState(false)
    const [error, setError] = useState("")
    const [dragOver, setDragOver] = useState(false)
    const [translationProgress, setTranslationProgress] = useState(0)
    const [translatedCount, setTranslatedCount] = useState(0)
    const [totalSegments, setTotalSegments] = useState(0)
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
    const [glossaries, setGlossaries] = useState<Array<{ glossary_id: string; version: string; is_active: boolean; meta_json?: { source_language?: string; target_language?: string } | null }>>([])
    const [selectedGlossary, setSelectedGlossary] = useState("")

    // Feature 1: Pipeline step tracking
    const [pipelineSteps, setPipelineSteps] = useState<AgentStep[]>([])
    const [currentStepId, setCurrentStepId] = useState<string | null>(null)
    const [batchInfo, setBatchInfo] = useState("")

    // Feature 4: Pre-translation estimate
    const [estimate, setEstimate] = useState<{
        total_llm_calls?: number
        estimated_total_tokens?: number
        estimated_cost_usd?: number
        estimated_seconds?: number
        model?: string
        tokens?: number
        cost_usd?: number
        segment_count?: number
        word_count?: number
    } | null>(null)
    const [showEstimateDialog, setShowEstimateDialog] = useState(false)

    // Cleanup polling on unmount
    useEffect(() => {
        return () => {
            if (pollRef.current) clearInterval(pollRef.current)
        }
    }, [])

    // Fetch active glossaries for the selector
    useEffect(() => {
        api.knowledge.listGlossaries().then(data => {
            setGlossaries((data as Array<{ glossary_id: string; version: string; is_active: boolean; meta_json?: { source_language?: string; target_language?: string } | null }>).filter(g => g.is_active))
        }).catch(() => {})
    }, [])

    const averageConfidence = segments.length > 0
        ? segments.reduce((sum, s) => sum + (s.confidence_score || 0), 0) / segments.filter(s => s.confidence_score).length
        : 0

    // --- Upload ---
    const handleFileUpload = async (file: File) => {
        setIsUploading(true)
        setError("")
        try {
            const srcLang = sourceLanguage === "auto" ? "en" : sourceLanguage
            const doc = await api.documents.upload(file, srcLang, targetLanguage, selectedGlossary || undefined)
            setDocument(doc)
            const segs = await api.segments.list(doc.id)
            setSegments(segs)
            setTotalSegments(segs.length)
            setState("uploaded")
        } catch (err) {
            setError(getErrMessage(err, "Failed to upload document."))
        } finally {
            setIsUploading(false)
        }
    }

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        setDragOver(false)
        const file = e.dataTransfer.files[0]
        if (file) handleFileUpload(file)
    }, [sourceLanguage, targetLanguage])

    // --- Feature 4: Pre-translation estimate ---
    const handleTranslateClick = async () => {
        if (!document) return
        setError("")
        try {
            const est = await api.documents.estimate(document.id)
            setEstimate(est)
            setShowEstimateDialog(true)
        } catch {
            // If estimate fails, start translation directly
            startTranslation()
        }
    }

    const confirmTranslation = () => {
        setShowEstimateDialog(false)
        setEstimate(null)
        startTranslation()
    }

    // --- Translate ---
    const startTranslation = async () => {
        if (!document) return
        setError("")
        setState("translating")
        setTranslationProgress(5)
        setTranslatedCount(0)

        // Feature 1: Initialize pipeline steps
        const batchSize = 5
        const totalBatches = Math.ceil(totalSegments / batchSize)
        const steps: AgentStep[] = [
            { id: "ingest-validate", label: "Validating document", status: "idle" },
            { id: "ingest-constraints", label: "Loading constraints & glossary", status: "idle" },
            { id: "translate-batches", label: `Translating (${totalBatches} batches)`, status: "idle" },
            { id: "gate-reflexion", label: "Quality gates & back-translation", status: "idle" },
            { id: "done-complete", label: "Finalizing", status: "idle" },
        ]
        steps[0].status = "active"
        setPipelineSteps(steps)
        setCurrentStepId("ingest-validate")

        // Feature 3: Track job for background notifications
        addActiveJob(document.id)
        toast.info("Translation started — you can navigate away", {
            description: "You'll be notified when it completes.",
            duration: 4000,
        })

        try {
            await api.documents.translate(document.id, targetLanguage)

            let lastProgressCount = 0
            let lastProgressTime = Date.now()

            pollRef.current = setInterval(async () => {
                try {
                    const doc = await api.documents.get(document.id)
                    const currentSegs = await api.segments.list(document.id)
                    const done = currentSegs.filter(s => s.translated_text && s.translated_text.length > 0).length

                    // Reset stall timer whenever progress advances
                    if (done > lastProgressCount || doc.status !== "processing") {
                        lastProgressCount = done
                        lastProgressTime = Date.now()
                    }

                    // Stall timeout: 5 minutes with no new segments translated
                    if (doc.status === "processing" && Date.now() - lastProgressTime > 300000) {
                        if (pollRef.current) {
                            clearInterval(pollRef.current)
                            pollRef.current = null
                            setError("Translation timed out. Check the document details page for status.")
                            setState("uploaded")
                        }
                        return
                    }

                    setTranslatedCount(done)
                    const pct = totalSegments > 0 ? Math.round((done / totalSegments) * 100) : 0
                    setTranslationProgress(Math.max(pct, 5))

                    // Feature 1: Derive pipeline step from progress
                    const currentBatch = Math.min(Math.ceil(done / batchSize), totalBatches)
                    setBatchInfo(`Batch ${currentBatch} of ${totalBatches} · ${done}/${totalSegments} segments · ${Math.max(pct, 5)}%`)

                    setPipelineSteps(prev => {
                        const updated = prev.map(s => ({ ...s }))
                        if (done === 0 && doc.status === "processing") {
                            // Early steps: validate/constraints
                            if (updated[0].status !== "done") {
                                updated[0].status = "done"
                                updated[1].status = "active"
                                updated[1].details = "Fetching glossary & TM matches"
                                setCurrentStepId("ingest-constraints")
                            }
                        } else if (done > 0 && done < totalSegments) {
                            // Translating batches
                            updated[0].status = "done"
                            updated[1].status = "done"
                            updated[2].status = "active"
                            updated[2].details = `Batch ${currentBatch} of ${totalBatches}`
                            setCurrentStepId("translate-batches")
                        } else if (done === totalSegments && doc.status === "processing") {
                            // Reflexion / back-translation
                            updated[0].status = "done"
                            updated[1].status = "done"
                            updated[2].status = "done"
                            updated[3].status = "active"
                            updated[3].details = "Running back-translation checks"
                            setCurrentStepId("gate-reflexion")
                        }
                        return updated
                    })

                    if (doc.status === "translated" || doc.status === "in_review" || doc.status === "approved") {
                        if (pollRef.current) clearInterval(pollRef.current)
                        setDocument(doc)
                        setSegments(currentSegs)
                        setTranslationProgress(100)
                        // Feature 1: Mark all steps done
                        setPipelineSteps(prev => prev.map(s => ({ ...s, status: "done" as const })))
                        setCurrentStepId("done-complete")
                        setState("done")
                        // Feature 3: Remove from background tracking
                        removeActiveJob(document.id)
                    } else if (doc.status === "uploaded") {
                        if (pollRef.current) clearInterval(pollRef.current)
                        setError("Translation failed. Please try again.")
                        setState("uploaded")
                        removeActiveJob(document.id)
                    }
                } catch {
                    // Keep polling
                }
            }, 2000)


        } catch (err) {
            setError(getErrMessage(err, "Translation failed."))
            setState("uploaded")
            if (document) removeActiveJob(document.id)
        }
    }

    // --- Download ---
    const handleDownload = async () => {
        if (!document) return
        try {
            const blob = await api.documents.downloadTranslated(document.id)
            const url = URL.createObjectURL(blob)
            const a = window.document.createElement("a")
            const ext = document.file_type === "txt" ? "txt" : "docx"
            a.href = url
            a.download = `${document.name.replace(/\.[^.]+$/, "")}_translated.${ext}`
            window.document.body.appendChild(a)
            a.click()
            window.document.body.removeChild(a)
            URL.revokeObjectURL(url)
        } catch (err) {
            setError(getErrMessage(err, "Download failed."))
        }
    }

    // --- Reset ---
    const resetFlow = () => {
        if (pollRef.current) clearInterval(pollRef.current)
        setState("idle")
        setDocument(null)
        setSegments([])
        setError("")
        setTranslationProgress(0)
        setTranslatedCount(0)
        setTotalSegments(0)
        setSelectedGlossary("")
    }

    // --- Remove uploaded file ---
    const removeFile = () => {
        setDocument(null)
        setSegments([])
        setState("idle")
    }

    return (
        <div style={{
            minHeight: "100vh",
            background: "#f8f9fa",
            fontFamily: "'Outfit', -apple-system, BlinkMacSystemFont, sans-serif"
        }}>
            {/* Header */}
            <header style={{
                background: "white",
                borderBottom: "1px solid #e5e5e5",
                padding: "1rem 2rem",
                position: "sticky",
                top: 0,
                zIndex: 100
            }}>
                <div style={{
                    maxWidth: "900px",
                    margin: "0 auto",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between"
                }}>
                    <Link href="/workspace" style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.5rem",
                        color: "#666",
                        textDecoration: "none",
                        fontSize: "0.9375rem"
                    }}>
                        <ArrowLeft size={18} />
                        <span>Back to Workspace</span>
                    </Link>

                    <h1 style={{
                        fontSize: "1.125rem",
                        fontWeight: 500,
                        color: "#202124",
                        margin: 0
                    }}>
                        Translate Document
                    </h1>

                    <div style={{ width: "160px" }} />
                </div>
            </header>

            {/* Main Content */}
            <main style={{
                maxWidth: "720px",
                margin: "0 auto",
                padding: "2rem 1.5rem"
            }}>
                {/* Language Bar */}
                <div style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "1rem",
                    padding: "1rem 1.5rem",
                    background: "white",
                    border: "1px solid #e0e0e0",
                    borderRadius: "12px",
                    marginBottom: "1.5rem"
                }}>
                    <LanguageSelector
                        value={sourceLanguage}
                        onChange={setSourceLanguage}
                        includeAuto
                    />
                    <button
                        onClick={() => {
                            if (sourceLanguage !== "auto") {
                                const tmp = sourceLanguage
                                setSourceLanguage(targetLanguage)
                                setTargetLanguage(tmp)
                            }
                        }}
                        disabled={sourceLanguage === "auto"}
                        style={{
                            background: "none",
                            border: "1px solid #dadce0",
                            borderRadius: "50%",
                            width: "36px",
                            height: "36px",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            cursor: sourceLanguage === "auto" ? "not-allowed" : "pointer",
                            color: sourceLanguage === "auto" ? "#ccc" : "#5f6368",
                            flexShrink: 0
                        }}
                        title="Swap languages"
                    >
                        <ArrowLeftRight size={16} />
                    </button>
                    <LanguageSelector
                        value={targetLanguage}
                        onChange={setTargetLanguage}
                    />
                </div>

                {/* Error Banner */}
                {error && (
                    <div style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.75rem",
                        padding: "1rem 1.25rem",
                        background: "#fef2f2",
                        border: "1px solid #fecaca",
                        borderRadius: "12px",
                        marginBottom: "1.5rem"
                    }}>
                        <AlertCircle size={20} style={{ color: "#dc2626" }} />
                        <span style={{ color: "#dc2626", flex: 1, fontSize: "0.9375rem" }}>{error}</span>
                        <button onClick={() => setError("")} style={{
                            background: "none",
                            border: "none",
                            color: "#dc2626",
                            cursor: "pointer",
                            padding: "4px"
                        }}>
                            <X size={18} />
                        </button>
                    </div>
                )}

                {/* ===== IDLE STATE ===== */}
                {state === "idle" && (
                    <div
                        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                        onDragLeave={() => setDragOver(false)}
                        onDrop={handleDrop}
                        style={{
                            position: "relative",
                            border: `2px dashed ${dragOver ? "#1a73e8" : "#dadce0"}`,
                            borderRadius: "16px",
                            padding: "4rem 2rem",
                            background: dragOver ? "#e8f0fe" : "white",
                            transition: "all 0.2s ease",
                            cursor: "pointer",
                            textAlign: "center"
                        }}
                    >
                        <input
                            type="file"
                            accept=".pdf,.docx,.txt"
                            onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
                            style={{
                                position: "absolute",
                                inset: 0,
                                opacity: 0,
                                cursor: "pointer"
                            }}
                        />

                        {isUploading ? (
                            <>
                                <Loader2 size={48} style={{
                                    color: "#1a73e8",
                                    animation: "spin 1s linear infinite"
                                }} />
                                <p style={{
                                    marginTop: "1.5rem",
                                    fontSize: "1.125rem",
                                    color: "#1a73e8",
                                    fontWeight: 500
                                }}>
                                    Uploading & extracting...
                                </p>
                            </>
                        ) : (
                            <>
                                <div style={{
                                    width: "80px",
                                    height: "80px",
                                    background: "linear-gradient(135deg, #e8f0fe, #d2e3fc)",
                                    borderRadius: "20px",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    margin: "0 auto 1.5rem"
                                }}>
                                    <Upload size={36} style={{ color: "#1a73e8" }} />
                                </div>
                                <p style={{
                                    fontSize: "1.125rem",
                                    fontWeight: 500,
                                    color: "#202124",
                                    marginBottom: "0.5rem"
                                }}>
                                    Drop your file here
                                </p>
                                <p style={{ color: "#5f6368", marginBottom: "1.5rem" }}>
                                    or click to browse your files
                                </p>
                                <div style={{
                                    display: "flex",
                                    justifyContent: "center",
                                    gap: "1.5rem",
                                    fontSize: "0.875rem",
                                    color: "#80868b"
                                }}>
                                    <span>.docx</span>
                                    <span>.pdf</span>
                                    <span>.txt</span>
                                </div>
                            </>
                        )}
                    </div>
                )}

                {/* ===== UPLOADED STATE ===== */}
                {state === "uploaded" && document && (
                    <div style={{
                        background: "white",
                        border: "1px solid #e0e0e0",
                        borderRadius: "16px",
                        padding: "2rem",
                        textAlign: "center"
                    }}>
                        <div style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "1rem",
                            padding: "1rem 1.25rem",
                            background: "#f8f9fa",
                            borderRadius: "12px",
                            marginBottom: "2rem",
                            textAlign: "left"
                        }}>
                            <div style={{
                                width: "48px",
                                height: "48px",
                                background: "linear-gradient(135deg, #4285f4, #1a73e8)",
                                borderRadius: "10px",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                flexShrink: 0
                            }}>
                                <FileText size={24} style={{ color: "white" }} />
                            </div>
                            <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{
                                    fontWeight: 500,
                                    color: "#202124",
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                    whiteSpace: "nowrap"
                                }}>
                                    {document.name}
                                </div>
                                <div style={{ fontSize: "0.875rem", color: "#5f6368" }}>
                                    {segments.length} segments · {document.word_count || 0} words
                                    {document.file_type === "pdf" && ` · ${document.page_count || 1} pages`}
                                </div>
                            </div>
                            <button
                                onClick={removeFile}
                                style={{
                                    background: "none",
                                    border: "none",
                                    cursor: "pointer",
                                    color: "#80868b",
                                    padding: "4px"
                                }}
                                title="Remove file"
                            >
                                <X size={20} />
                            </button>
                        </div>

                        {document.file_type === "pdf" && (
                            <div style={{
                                padding: "0.75rem 1rem",
                                background: "#fef7e0",
                                border: "1px solid #fdd835",
                                borderRadius: "8px",
                                fontSize: "0.8125rem",
                                color: "#795500",
                                marginBottom: "1.5rem",
                                textAlign: "left"
                            }}>
                                PDF files will be exported as DOCX to preserve translated text formatting.
                            </div>
                        )}

                        {/* Glossary Selector */}
                        {glossaries.length > 0 && (
                            <div style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "0.75rem",
                                padding: "0.75rem 1.25rem",
                                background: "#f8f9fa",
                                borderRadius: "10px",
                                marginBottom: "1.5rem",
                                textAlign: "left"
                            }}>
                                <BookOpen size={18} style={{ color: "#5f6368", flexShrink: 0 }} />
                                <div style={{ flex: 1 }}>
                                    <div style={{ fontSize: "0.75rem", color: "#80868b", marginBottom: "0.25rem" }}>Glossary (optional)</div>
                                    <select
                                        value={selectedGlossary}
                                        onChange={e => setSelectedGlossary(e.target.value)}
                                        style={{
                                            width: "100%",
                                            padding: "0.375rem 0.5rem",
                                            border: "1px solid #dadce0",
                                            borderRadius: "6px",
                                            fontSize: "0.875rem",
                                            background: "white",
                                            color: "#202124",
                                            outline: "none"
                                        }}
                                    >
                                        <option value="">None</option>
                                        {glossaries
                                            .filter(g => !targetLanguage || !g.meta_json?.target_language || g.meta_json.target_language === targetLanguage)
                                            .map(g => (
                                                <option key={`${g.glossary_id}:${g.version}`} value={g.glossary_id}>
                                                    {g.glossary_id} (v{g.version}){g.meta_json?.target_language ? ` — ${g.meta_json.source_language} → ${g.meta_json.target_language}` : ""}
                                                </option>
                                            ))
                                        }
                                    </select>
                                </div>
                            </div>
                        )}

                        <button
                            onClick={handleTranslateClick}
                            disabled={segments.length === 0}
                            style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "0.625rem",
                                padding: "0.875rem 2.5rem",
                                background: segments.length > 0
                                    ? "linear-gradient(135deg, #4285f4, #1a73e8)"
                                    : "#e0e0e0",
                                color: segments.length > 0 ? "white" : "#9aa0a6",
                                border: "none",
                                borderRadius: "28px",
                                fontSize: "1rem",
                                fontWeight: 500,
                                cursor: segments.length > 0 ? "pointer" : "not-allowed",
                                boxShadow: segments.length > 0
                                    ? "0 4px 14px rgba(26, 115, 232, 0.3)"
                                    : "none"
                            }}
                        >
                            <Languages size={18} />
                            Translate
                        </button>
                    </div>
                )}

                {/* ===== TRANSLATING STATE ===== */}
                {state === "translating" && (
                    <div style={{
                        background: "white",
                        border: "1px solid #e0e0e0",
                        borderRadius: "16px",
                        padding: "3rem 2rem",
                        textAlign: "center"
                    }}>
                        <Loader2 size={48} style={{
                            color: "#1a73e8",
                            animation: "spin 1s linear infinite",
                            marginBottom: "1.5rem"
                        }} />
                        <h2 style={{
                            fontSize: "1.25rem",
                            fontWeight: 500,
                            color: "#202124",
                            marginBottom: "0.75rem"
                        }}>
                            Translating...
                        </h2>

                        {/* Progress bar */}
                        <div style={{
                            maxWidth: "400px",
                            margin: "0 auto 1rem"
                        }}>
                            <div style={{
                                height: "8px",
                                background: "#e8eaed",
                                borderRadius: "4px",
                                overflow: "hidden"
                            }}>
                                <div style={{
                                    height: "100%",
                                    width: `${translationProgress}%`,
                                    background: "linear-gradient(90deg, #4285f4, #1a73e8)",
                                    borderRadius: "4px",
                                    transition: "width 0.5s ease"
                                }} />
                            </div>
                        </div>
                        <p style={{
                            fontSize: "0.9375rem",
                            color: "#5f6368",
                            margin: 0
                        }}>
                            {batchInfo || `${translatedCount} / ${totalSegments} segments · ${translationProgress}%`}
                        </p>
                        <p style={{
                            fontSize: "0.8125rem",
                            color: "#80868b",
                            marginTop: "0.5rem"
                        }}>
                            You can navigate away — we&apos;ll notify you when it&apos;s done.
                        </p>

                        {/* Feature 1: LiveIsland pipeline tracker */}
                        {pipelineSteps.length > 0 && (
                            <LiveIsland steps={pipelineSteps} currentStepId={currentStepId} />
                        )}
                    </div>
                )}

                {/* ===== DONE STATE ===== */}
                {state === "done" && document && (
                    <div style={{
                        background: "white",
                        border: "1px solid #e0e0e0",
                        borderRadius: "16px",
                        overflow: "hidden"
                    }}>
                        {/* Success header */}
                        <div style={{
                            padding: "2rem",
                            textAlign: "center",
                            borderBottom: "1px solid #f0f0f0"
                        }}>
                            <div style={{
                                width: "56px",
                                height: "56px",
                                background: "#e6f4ea",
                                borderRadius: "50%",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                margin: "0 auto 1rem"
                            }}>
                                <CheckCircle2 size={28} style={{ color: "#1e8e3e" }} />
                            </div>
                            <h2 style={{
                                fontSize: "1.25rem",
                                fontWeight: 500,
                                color: "#202124",
                                marginBottom: "0.5rem"
                            }}>
                                Translation complete
                            </h2>
                            <p style={{ color: "#5f6368", margin: 0, fontSize: "0.9375rem" }}>
                                {segments.length} segments · {averageConfidence > 0 ? `${Math.round(averageConfidence * 100)}% confidence` : ""}
                                {" · "}{getLanguageName(document.source_language)} → {getLanguageName(targetLanguage)}
                            </p>
                        </div>

                        {/* Preview of translated text */}
                        <div style={{
                            maxHeight: "320px",
                            overflowY: "auto",
                            padding: "0"
                        }}>
                            {segments.filter(s => s.translated_text).slice(0, 20).map((seg) => (
                                <div key={seg.id} style={{
                                    padding: "1rem 1.5rem",
                                    borderBottom: "1px solid #f5f5f5",
                                    display: "grid",
                                    gridTemplateColumns: "1fr 1fr",
                                    gap: "1.5rem"
                                }}>
                                    <p style={{
                                        margin: 0,
                                        fontSize: "0.875rem",
                                        lineHeight: 1.6,
                                        color: "#80868b"
                                    }}>
                                        {seg.source_text}
                                    </p>
                                    <p style={{
                                        margin: 0,
                                        fontSize: "0.875rem",
                                        lineHeight: 1.6,
                                        color: "#202124"
                                    }}>
                                        {seg.translated_text}
                                    </p>
                                </div>
                            ))}
                            {segments.filter(s => s.translated_text).length > 20 && (
                                <div style={{
                                    padding: "0.75rem 1.5rem",
                                    textAlign: "center",
                                    color: "#5f6368",
                                    fontSize: "0.8125rem"
                                }}>
                                    ... and {segments.filter(s => s.translated_text).length - 20} more segments
                                </div>
                            )}
                        </div>

                        {/* Action buttons */}
                        <div style={{
                            display: "flex",
                            justifyContent: "center",
                            gap: "0.75rem",
                            padding: "1.5rem 2rem",
                            borderTop: "1px solid #f0f0f0",
                            flexWrap: "wrap"
                        }}>
                            <button
                                onClick={handleDownload}
                                style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    gap: "0.5rem",
                                    padding: "0.75rem 1.5rem",
                                    background: "linear-gradient(135deg, #1e8e3e, #188038)",
                                    color: "white",
                                    border: "none",
                                    borderRadius: "28px",
                                    fontSize: "0.9375rem",
                                    fontWeight: 500,
                                    cursor: "pointer",
                                    boxShadow: "0 4px 14px rgba(30, 142, 62, 0.3)"
                                }}
                            >
                                <Download size={16} />
                                {document.file_type === "docx"
                                    ? "Download .docx (original formatting preserved)"
                                    : document.file_type === "pdf"
                                        ? "Download as .docx (formatted)"
                                        : "Download .txt"}
                            </button>
                            <button
                                onClick={() => router.push(`/workspace/documents/${document.id}`)}
                                style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    gap: "0.5rem",
                                    padding: "0.75rem 1.5rem",
                                    background: "white",
                                    border: "1px solid #dadce0",
                                    borderRadius: "28px",
                                    fontSize: "0.9375rem",
                                    color: "#5f6368",
                                    cursor: "pointer"
                                }}
                            >
                                <ExternalLink size={16} />
                                View Details
                            </button>
                            <button
                                onClick={resetFlow}
                                style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    gap: "0.5rem",
                                    padding: "0.75rem 1.5rem",
                                    background: "white",
                                    border: "1px solid #dadce0",
                                    borderRadius: "28px",
                                    fontSize: "0.9375rem",
                                    color: "#5f6368",
                                    cursor: "pointer"
                                }}
                            >
                                <RotateCcw size={16} />
                                Translate Another
                            </button>
                        </div>
                    </div>
                )}
                {/* ===== Feature 4: ESTIMATE DIALOG ===== */}
                {showEstimateDialog && estimate && (
                    <div style={{
                        position: "fixed",
                        inset: 0,
                        background: "rgba(0,0,0,0.4)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        zIndex: 200
                    }}>
                        <div style={{
                            background: "white",
                            borderRadius: "16px",
                            padding: "2rem",
                            maxWidth: "480px",
                            width: "90%",
                            boxShadow: "0 20px 60px rgba(0,0,0,0.2)"
                        }}>
                            <h3 style={{ fontSize: "1.125rem", fontWeight: 600, color: "#202124", marginBottom: "1.25rem" }}>
                                Translation Estimate
                            </h3>
                            <div style={{
                                display: "grid",
                                gridTemplateColumns: "1fr 1fr",
                                gap: "1rem",
                                marginBottom: "1.5rem"
                            }}>
                                {[
                                    { label: "Segments", value: estimate.segment_count },
                                    { label: "Words", value: estimate.word_count?.toLocaleString() },
                                    { label: "LLM Calls", value: estimate.total_llm_calls },
                                    { label: "Est. Tokens", value: estimate.estimated_total_tokens?.toLocaleString() },
                                    { label: "Est. Cost", value: `$${estimate.estimated_cost_usd?.toFixed(4)}` },
                                    { label: "Est. Time", value: `~${Math.ceil((estimate.estimated_seconds || 0) / 60)} min` },
                                ].map(item => (
                                    <div key={item.label} style={{
                                        padding: "0.75rem 1rem",
                                        background: "#f8f9fa",
                                        borderRadius: "10px"
                                    }}>
                                        <div style={{ fontSize: "0.75rem", color: "#80868b", marginBottom: "0.25rem" }}>{item.label}</div>
                                        <div style={{ fontSize: "1rem", fontWeight: 600, color: "#202124" }}>{item.value ?? "—"}</div>
                                    </div>
                                ))}
                            </div>
                            <div style={{ fontSize: "0.75rem", color: "#80868b", marginBottom: "1rem" }}>
                                Model: {estimate.model || "gpt-4o-mini"} · Batch size: 5 segments
                            </div>
                            <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end" }}>
                                <button
                                    onClick={() => { setShowEstimateDialog(false); setEstimate(null) }}
                                    style={{
                                        padding: "0.625rem 1.25rem",
                                        background: "white",
                                        border: "1px solid #dadce0",
                                        borderRadius: "8px",
                                        fontSize: "0.875rem",
                                        cursor: "pointer",
                                        color: "#5f6368"
                                    }}
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={confirmTranslation}
                                    style={{
                                        padding: "0.625rem 1.25rem",
                                        background: "linear-gradient(135deg, #4285f4, #1a73e8)",
                                        color: "white",
                                        border: "none",
                                        borderRadius: "8px",
                                        fontSize: "0.875rem",
                                        fontWeight: 500,
                                        cursor: "pointer",
                                        boxShadow: "0 2px 8px rgba(26, 115, 232, 0.3)"
                                    }}
                                >
                                    Start Translation
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </main>

            <style jsx global>{`
                @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    )
}
