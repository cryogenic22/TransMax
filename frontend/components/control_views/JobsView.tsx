"use client"

import { useState, useEffect, useMemo } from "react"
import {
    Clock, CheckCircle2, AlertCircle, Play, RefreshCw, FileText,
    Search, Target, WifiOff, Download, Trash2,
    ChevronDown, ChevronUp, X
} from "lucide-react"
import Link from "next/link"
import { api, Document, DeletionRecord } from "@/lib/api"
import { ConfidenceMeter } from "@/components/ui/ConfidenceMeter"

interface EnrichedJob {
    id: string
    document_id: string
    document_name: string
    file_type: string
    target_language: string
    source_language: string
    status: string
    progress: number
    segment_count: number
    translated_count: number
    quality_status?: string
    confidence_score?: number
    score_breakdown?: any
    created_at: string
    completed_at?: string
    duration?: string
}

const LANGUAGE_NAMES: Record<string, string> = {
    'en': 'English', 'de': 'German', 'fr': 'French', 'es': 'Spanish',
    'it': 'Italian', 'pt': 'Portuguese', 'nl': 'Dutch', 'ja': 'Japanese',
    'zh': 'Chinese', 'ko': 'Korean'
}

export function JobsView() {
    const [jobs, setJobs] = useState<EnrichedJob[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [searchQuery, setSearchQuery] = useState("")
    const [statusFilter, setStatusFilter] = useState<string>("all")

    // Delete confirmation state
    const [deleteTarget, setDeleteTarget] = useState<EnrichedJob | null>(null)
    const [deleteReason, setDeleteReason] = useState("")
    const [deleting, setDeleting] = useState(false)

    // Deletion log state
    const [deletionLog, setDeletionLog] = useState<DeletionRecord[]>([])
    const [showDeletionLog, setShowDeletionLog] = useState(false)

    const fetchJobs = async () => {
        setLoading(true)
        setError(null)
        try {
            const docs = await api.documents.list()
            const enrichedJobs: EnrichedJob[] = await Promise.all(docs.items.map(async (doc: Document) => {
                let translatedCount = 0
                let segmentCount = doc.segment_count || 0
                if (doc.status !== 'uploaded') {
                    try {
                        const segments = await api.segments.list(doc.id)
                        segmentCount = segments.length
                        translatedCount = segments.filter((s: any) => s.translated_text).length
                    } catch { }
                }
                let jobStatus = 'queued'
                if (doc.status === 'translated' || doc.status === 'approved' || doc.status === 'in_review') jobStatus = 'completed'
                else if (doc.status === 'processing') jobStatus = 'processing'
                else if (doc.status === 'uploaded') jobStatus = 'queued'
                const progress = segmentCount > 0 ? Math.round((translatedCount / segmentCount) * 100) : 0
                return {
                    id: doc.id, document_id: doc.id, document_name: doc.name || 'Untitled Document',
                    file_type: doc.file_type || 'pdf', target_language: doc.target_language || '',
                    source_language: doc.source_language || 'en', status: jobStatus,
                    progress: jobStatus === 'completed' ? 100 : progress,
                    segment_count: segmentCount, translated_count: translatedCount,
                    quality_status: doc.status === 'in_review' ? 'review_required' : 'passed',
                    confidence_score: doc.confidence_score, score_breakdown: (doc as any).score_breakdown,
                    created_at: doc.created_at, completed_at: doc.updated_at
                }
            }))
            enrichedJobs.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
            setJobs(enrichedJobs)
        } catch (err: any) {
            console.error(err)
            setError(err.message || "Failed to load jobs")
            setJobs([])
        } finally {
            setLoading(false)
        }
    }

    const handleDelete = async () => {
        if (!deleteTarget) return
        setDeleting(true)
        try {
            await api.documents.delete(deleteTarget.document_id, deleteReason || undefined)
            setJobs(prev => prev.filter(j => j.id !== deleteTarget.id))
            setDeleteTarget(null)
            setDeleteReason("")
            // Refresh deletion log if visible
            if (showDeletionLog) fetchDeletionLog()
        } catch (err: any) {
            console.error("Delete failed:", err)
        } finally {
            setDeleting(false)
        }
    }

    const fetchDeletionLog = async () => {
        try {
            const records = await api.documents.listDeletions()
            setDeletionLog(records)
        } catch (err) {
            console.error("Failed to load deletion log:", err)
        }
    }

    useEffect(() => { fetchJobs() }, [])

    useEffect(() => {
        if (showDeletionLog) fetchDeletionLog()
    }, [showDeletionLog])

    const filteredJobs = useMemo(() => {
        return jobs.filter(job => {
            const matchesSearch = searchQuery === "" ||
                job.document_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                job.target_language.toLowerCase().includes(searchQuery.toLowerCase())
            const matchesStatus = statusFilter === "all" || job.status === statusFilter
            return matchesSearch && matchesStatus
        })
    }, [jobs, searchQuery, statusFilter])

    const getStatusBadge = (status: string) => {
        const styles: Record<string, any> = {
            completed: { bg: "bg-green-100", text: "text-green-800", icon: <CheckCircle2 size={14} /> },
            processing: { bg: "bg-blue-100", text: "text-blue-800", icon: <Play size={14} /> },
            queued: { bg: "bg-slate-100", text: "text-slate-600", icon: <Clock size={14} /> },
            failed: { bg: "bg-red-50", text: "text-red-600", icon: <AlertCircle size={14} /> }
        }
        const s = styles[status] || styles.queued
        return (
            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${s.bg} ${s.text}`}>
                {s.icon} {status.charAt(0).toUpperCase() + status.slice(1)}
            </span>
        )
    }

    if (loading) return <div className="p-12 text-center text-slate-500">Loading jobs...</div>

    if (error) return (
        <div className="text-center py-12 bg-white rounded-xl border border-amber-200">
            <div className="w-16 h-16 bg-amber-50 rounded-full flex items-center justify-center mx-auto mb-4">
                <WifiOff className="text-amber-600" size={28} />
            </div>
            <h3 className="text-lg font-semibold text-slate-900 mb-2">Unable to load jobs</h3>
            <p className="text-slate-500 text-sm mb-4 max-w-md mx-auto">{error}</p>
            <button onClick={fetchJobs} className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors">
                <RefreshCw size={14} /> Retry
            </button>
        </div>
    )

    return (
        <div className="space-y-6">
            {/* Filters */}
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row gap-4 items-center">
                <div className="relative flex-1 w-full">
                    <Search className="absolute left-3 top-2.5 text-slate-400" size={18} />
                    <input
                        type="text"
                        placeholder="Search jobs..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                    />
                </div>
                <div className="flex gap-2">
                    {['all', 'completed', 'processing', 'queued'].map(status => (
                        <button
                            key={status}
                            onClick={() => setStatusFilter(status)}
                            className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${statusFilter === status ? 'bg-blue-50 text-blue-700' : 'hover:bg-slate-50 text-slate-600'
                                }`}
                        >
                            {status}
                        </button>
                    ))}
                    <button onClick={fetchJobs} className="p-2 text-slate-400 hover:text-blue-600 hover:bg-slate-50 rounded-lg">
                        <RefreshCw size={20} />
                    </button>
                </div>
            </div>

            {/* List */}
            {filteredJobs.length === 0 ? (
                <div className="text-center py-12 bg-white rounded-xl border border-slate-200 border-dashed">
                    <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mx-auto mb-4">
                        <FileText className="text-slate-400" size={32} />
                    </div>
                    <h3 className="text-lg font-semibold text-slate-900">No jobs found</h3>
                    <p className="text-slate-500">Adjust filters or upload a document to get started.</p>
                </div>
            ) : (
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                    <table className="w-full text-left">
                        <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                            <tr>
                                <th className="px-6 py-3">Document</th>
                                <th className="px-6 py-3">Target</th>
                                <th className="px-6 py-3">Progress</th>
                                <th className="px-6 py-3">Risk</th>
                                <th className="px-6 py-3">Status</th>
                                <th className="px-6 py-3">Date</th>
                                <th className="px-6 py-3 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {filteredJobs.map(job => (
                                <tr key={job.id} className="hover:bg-slate-50 transition-colors group">
                                    <td className="px-6 py-4">
                                        <div className="flex items-center gap-3">
                                            <div className="w-8 h-8 rounded bg-blue-50 flex items-center justify-center text-blue-600">
                                                <FileText size={16} />
                                            </div>
                                            <div>
                                                <div className="font-medium text-slate-900">{job.document_name}</div>
                                                <div className="text-xs text-slate-500 uppercase">{job.file_type}</div>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="flex items-center gap-2 text-sm text-slate-700 font-medium">
                                            <Target size={14} className="text-slate-400" />
                                            {LANGUAGE_NAMES[job.target_language] || job.target_language}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="w-32">
                                            <div className="flex justify-between text-xs mb-1">
                                                <span>{job.progress}%</span>
                                                <span className="text-slate-400">{job.translated_count}/{job.segment_count}</span>
                                            </div>
                                            <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                                                <div className="h-full bg-green-500 rounded-full transition-all duration-500" style={{ width: `${job.progress}%` }} />
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4">
                                        {job.confidence_score ? <ConfidenceMeter score={job.confidence_score} /> : <span className="text-xs text-slate-400">—</span>}
                                    </td>
                                    <td className="px-6 py-4">
                                        {getStatusBadge(job.status)}
                                    </td>
                                    <td className="px-6 py-4 text-sm text-slate-500">
                                        {new Date(job.created_at).toLocaleDateString()}
                                    </td>
                                    <td className="px-6 py-4 text-right">
                                        <div className="flex items-center justify-end gap-3">
                                            {job.status === "completed" && (
                                                <button
                                                    onClick={async (e) => {
                                                        e.preventDefault()
                                                        try {
                                                            const blob = await api.documents.downloadTranslated(job.document_id)
                                                            const url = URL.createObjectURL(blob)
                                                            const a = window.document.createElement("a")
                                                            const ext = job.file_type === "txt" ? "txt" : "docx"
                                                            a.href = url
                                                            a.download = `${job.document_name.replace(/\.[^.]+$/, "")}_translated.${ext}`
                                                            window.document.body.appendChild(a)
                                                            a.click()
                                                            a.remove()
                                                            URL.revokeObjectURL(url)
                                                        } catch (err) {
                                                            console.error("Download failed:", err)
                                                        }
                                                    }}
                                                    className="text-slate-500 hover:text-blue-600 transition-colors"
                                                    title="Download translated document"
                                                >
                                                    <Download size={16} />
                                                </button>
                                            )}
                                            <button
                                                onClick={() => setDeleteTarget(job)}
                                                className="text-slate-400 hover:text-red-600 transition-colors"
                                                title="Delete document"
                                            >
                                                <Trash2 size={16} />
                                            </button>
                                            <Link href={`/workspace/documents/${job.document_id}`} className="text-blue-600 hover:text-blue-800 text-sm font-medium hover:underline">
                                                Open
                                            </Link>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Deletion Log Panel */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                <button
                    onClick={() => setShowDeletionLog(!showDeletionLog)}
                    className="w-full px-6 py-3 flex items-center justify-between text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
                >
                    <span>Deletion Log</span>
                    {showDeletionLog ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </button>
                {showDeletionLog && (
                    <div className="border-t border-slate-200">
                        {deletionLog.length === 0 ? (
                            <div className="px-6 py-8 text-center text-sm text-slate-400">No deletion records found.</div>
                        ) : (
                            <table className="w-full text-left text-sm">
                                <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                    <tr>
                                        <th className="px-6 py-2">Document</th>
                                        <th className="px-6 py-2">Status Before</th>
                                        <th className="px-6 py-2">Segments</th>
                                        <th className="px-6 py-2">Reason</th>
                                        <th className="px-6 py-2">Deleted At</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {deletionLog.map(rec => (
                                        <tr key={rec.id} className="text-slate-600">
                                            <td className="px-6 py-2 font-medium text-slate-900">{rec.document_name}</td>
                                            <td className="px-6 py-2 capitalize">{rec.status_before_delete}</td>
                                            <td className="px-6 py-2">{rec.segment_count}</td>
                                            <td className="px-6 py-2 text-slate-500 max-w-xs truncate">{rec.reason || "—"}</td>
                                            <td className="px-6 py-2">{new Date(rec.deleted_at).toLocaleString()}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                )}
            </div>

            {/* Delete Confirmation Dialog */}
            {deleteTarget && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
                    <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
                        <div className="flex items-center justify-between">
                            <h3 className="text-lg font-semibold text-slate-900">Delete Document</h3>
                            <button onClick={() => { setDeleteTarget(null); setDeleteReason("") }} className="text-slate-400 hover:text-slate-600">
                                <X size={20} />
                            </button>
                        </div>
                        <p className="text-sm text-slate-600">
                            Are you sure you want to delete <span className="font-semibold">{deleteTarget.document_name}</span>? This action cannot be undone.
                        </p>
                        <textarea
                            placeholder="Reason for deletion (optional)"
                            value={deleteReason}
                            onChange={e => setDeleteReason(e.target.value)}
                            className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500/20 resize-none"
                            rows={3}
                        />
                        <div className="flex justify-end gap-3">
                            <button
                                onClick={() => { setDeleteTarget(null); setDeleteReason("") }}
                                className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 rounded-lg"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleDelete}
                                disabled={deleting}
                                className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50"
                            >
                                {deleting ? "Deleting..." : "Delete"}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
