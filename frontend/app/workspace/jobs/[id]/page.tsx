"use client"

import { useEffect, useState, useCallback, Suspense } from "react"
import { useParams, useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, FileText, Globe, Loader2 } from "lucide-react"
import { api, Document, Segment } from "@/lib/api"
import {
    StatusLifecycle,
    type LifecycleStatus,
} from "@/components/ui/StatusLifecycle"
import { ProvenanceChip } from "@/components/ui/ProvenanceChip"
import { AgentLanes, type AgentActivity } from "@/components/ui/AgentLanes"
import { RevisionIndicator } from "@/components/ui/RevisionIndicator"
import { useAgentActivityByJob } from "@/hooks/useActivity"
import { getErrMessage } from "@/lib/utils"

// TMX-3603-jobs-id: canonical detail page for a single job. The legacy
// /translate/:jobId and /review/:jobId routes 308-redirect into this page
// with `?mode=translate` or `?mode=review` selecting the active section.

type Mode = "overview" | "translate" | "review"

const DOC_STATUS_TO_LIFECYCLE: Record<string, LifecycleStatus> = {
    uploaded: "pending",
    processing: "translating",
    translated: "translated",
    in_review: "reviewed",
    approved: "approved",
    blocked: "blocked",
}

export default function WorkspaceJobDetailPage() {
    return (
        <Suspense fallback={<DetailLoading />}>
            <WorkspaceJobDetailInner />
        </Suspense>
    )
}

function DetailLoading() {
    return (
        <div className="flex items-center justify-center py-20 text-slate-400">
            <Loader2 className="animate-spin mr-2" size={20} />
            Loading job…
        </div>
    )
}

function WorkspaceJobDetailInner() {
    const params = useParams()
    const router = useRouter()
    const searchParams = useSearchParams()
    const jobId = params.id as string
    const modeParam = searchParams.get("mode")
    const mode: Mode =
        modeParam === "translate" || modeParam === "review" ? modeParam : "overview"

    const [doc, setDoc] = useState<Document | null>(null)
    const [segments, setSegments] = useState<Segment[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    // TMX-3603-jobs-id: backend resolves job_id → audit_id internally so
    // this hook delivers the AgentLanes data without knowing the audit_id.
    const { data: agentActivities } = useAgentActivityByJob(jobId)

    const fetchData = useCallback(async () => {
        try {
            const [d, segs] = await Promise.all([
                api.documents.get(jobId).catch(() => null),
                api.segments.list(jobId).catch(() => [] as Segment[]),
            ])
            setDoc(d)
            setSegments(segs)
        } catch (err) {
            setError(getErrMessage(err, "Failed to load job"))
        } finally {
            setLoading(false)
        }
    }, [jobId])

    useEffect(() => {
        fetchData()
    }, [fetchData])

    if (loading) return <DetailLoading />

    if (error || !doc) {
        return (
            <div className="max-w-2xl mx-auto p-6">
                <Link href="/workspace/jobs" className="text-sm text-slate-500 hover:text-slate-800 inline-flex items-center gap-1 mb-4">
                    <ArrowLeft size={14} /> Back to Jobs
                </Link>
                <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                    {error ?? "Job not found."}
                </div>
            </div>
        )
    }

    const lifecycle = DOC_STATUS_TO_LIFECYCLE[doc.status] ?? "pending"
    const translatedCount = segments.filter(s => s.translated_text).length
    const reviewedCount = segments.filter(s => s.status === "approved" || s.status === "edited").length

    return (
        <main className="max-w-5xl mx-auto p-6 space-y-6">
            <div>
                <Link href="/workspace/jobs" className="text-sm text-slate-500 hover:text-slate-800 inline-flex items-center gap-1 mb-3">
                    <ArrowLeft size={14} /> Back to Jobs
                </Link>
                <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div className="space-y-1">
                        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
                            <FileText size={22} className="text-slate-400" />
                            {doc.name}
                        </h1>
                        <div className="flex items-center gap-2 flex-wrap">
                            <StatusLifecycle status={lifecycle} />
                            <span className="text-sm text-muted-foreground inline-flex items-center gap-1">
                                <Globe size={12} /> {doc.source_language} → {doc.target_language || "—"}
                            </span>
                            <ProvenanceChip
                                source="job"
                                version={doc.id.slice(0, 8)}
                                timestamp={doc.updated_at}
                            />
                        </div>
                    </div>
                </div>
            </div>

            <ModeTabs jobId={jobId} active={mode} onChange={m => router.push(`/workspace/jobs/${jobId}${m === "overview" ? "" : `?mode=${m}`}`)} />

            {mode === "overview" && (
                <Overview
                    doc={doc}
                    segments={segments}
                    translatedCount={translatedCount}
                    reviewedCount={reviewedCount}
                    agentActivities={agentActivities ?? []}
                />
            )}
            {mode === "translate" && (
                <TranslateView doc={doc} agentActivities={agentActivities ?? []} />
            )}
            {mode === "review" && (
                <ReviewView segments={segments} />
            )}
        </main>
    )
}

function ModeTabs({ jobId: _jobId, active, onChange }: { jobId: string; active: Mode; onChange: (m: Mode) => void }) {
    const tabs: Array<{ id: Mode; label: string }> = [
        { id: "overview", label: "Overview" },
        { id: "translate", label: "Translate" },
        { id: "review", label: "Review" },
    ]
    return (
        <div className="flex border-b border-slate-200">
            {tabs.map(t => (
                <button
                    key={t.id}
                    type="button"
                    onClick={() => onChange(t.id)}
                    className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                        active === t.id
                            ? "border-blue-600 text-blue-700"
                            : "border-transparent text-slate-500 hover:text-slate-800"
                    }`}
                >
                    {t.label}
                </button>
            ))}
        </div>
    )
}

function Overview({
    doc,
    segments,
    translatedCount,
    reviewedCount,
    agentActivities,
}: {
    doc: Document
    segments: Segment[]
    translatedCount: number
    reviewedCount: number
    agentActivities: AgentActivity[]
}) {
    return (
        <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <Stat label="Segments" value={`${segments.length}`} />
                <Stat label="Translated" value={`${translatedCount} / ${segments.length}`} />
                <Stat label="Reviewed" value={`${reviewedCount} / ${segments.length}`} />
                <Stat label="Confidence" value={doc.confidence_score != null ? `${Math.round(doc.confidence_score * 100)}%` : "—"} />
            </div>
            <section className="space-y-2">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Agents</h2>
                <AgentLanes activities={agentActivities} />
            </section>
        </div>
    )
}

function TranslateView({ doc, agentActivities }: { doc: Document; agentActivities: AgentActivity[] }) {
    return (
        <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
                Live multi-agent pipeline for <strong>{doc.name}</strong>. Each lane shows the
                in-flight or completed work from the four canonical agents.
            </p>
            <AgentLanes activities={agentActivities} />
        </div>
    )
}

function ReviewView({ segments }: { segments: Segment[] }) {
    if (segments.length === 0) {
        return (
            <div className="rounded-lg border bg-card px-4 py-6 text-center text-sm text-muted-foreground">
                No segments to review yet.
            </div>
        )
    }
    return (
        <ol className="space-y-3">
            {segments.map(seg => (
                <li key={seg.id} className="rounded-lg border bg-card p-4 text-sm">
                    <div className="flex items-center justify-between gap-2 mb-2">
                        <span className="text-xs text-slate-500 font-mono">#{seg.order_index}</span>
                        <div className="flex items-center gap-2 flex-wrap">
                            {/* TMX-3702-v1: surface DOCX tracked-changes when present.
                                Captured by TMX-3700; persisted in Segment.element_meta. */}
                            {seg.element_meta?.revisions ? (
                                <RevisionIndicator revisions={seg.element_meta.revisions} />
                            ) : null}
                            <StatusLifecycle status={mapSegmentStatus(seg.status)} />
                        </div>
                    </div>
                    <p className="text-slate-600 mb-1"><span className="text-xs uppercase tracking-wide text-slate-400">Source · </span>{seg.source_text}</p>
                    {seg.translated_text ? (
                        <p className="text-slate-900"><span className="text-xs uppercase tracking-wide text-slate-400">Target · </span>{seg.translated_text}</p>
                    ) : (
                        <p className="text-slate-400 italic">Awaiting translation.</p>
                    )}
                </li>
            ))}
        </ol>
    )
}

function mapSegmentStatus(s: Segment["status"]): LifecycleStatus {
    switch (s) {
        case "pending": return "pending"
        case "translated": return "translated"
        case "edited": return "reviewed"
        case "approved": return "approved"
        case "blocked": return "blocked"
        default: return "pending"
    }
}

function Stat({ label, value }: { label: string; value: string }) {
    return (
        <div className="rounded-lg border bg-card px-4 py-3">
            <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</div>
            <div className="text-lg font-semibold text-slate-900 leading-tight">{value}</div>
        </div>
    )
}
