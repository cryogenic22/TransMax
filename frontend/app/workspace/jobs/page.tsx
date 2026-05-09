"use client"

import { useState, useEffect, useMemo } from "react"
import {
    Clock, CheckCircle2, AlertCircle, Play, RefreshCw, FileText, Languages,
    Search, Eye, ArrowUpRight, Zap, Target, WifiOff
} from "lucide-react"
import Link from "next/link"
import { api, Document } from "@/lib/api"
import { ConfidenceMeter } from "@/components/ui/ConfidenceMeter"
import { getErrMessage } from "@/lib/utils"

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
    score_breakdown?: {
        base?: number
        deterministic_penalty?: number
        semantic_penalty?: number
        structural_penalty?: number
        process_penalty?: number
    }
    created_at: string
    completed_at?: string
    duration?: string
}

const LANGUAGE_NAMES: Record<string, string> = {
    'en': 'English',
    'de': 'German',
    'fr': 'French',
    'es': 'Spanish',
    'it': 'Italian',
    'pt': 'Portuguese',
    'nl': 'Dutch',
    'ja': 'Japanese',
    'zh': 'Chinese',
    'ko': 'Korean'
}

export default function JobsPage() {
    const [jobs, setJobs] = useState<EnrichedJob[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [searchQuery, setSearchQuery] = useState("")
    const [statusFilter, setStatusFilter] = useState<string>("all")

    const fetchJobs = async () => {
        setLoading(true)
        setError(null)
        try {
            // Fetch documents - they represent the "jobs" in our system
            const docs = await api.documents.list()

            // Transform documents into enriched jobs with all the info we need
            const enrichedJobs: EnrichedJob[] = await Promise.all(docs.items.map(async (doc: Document) => {
                let translatedCount = 0
                let segmentCount = doc.segment_count || 0

                // Fetch segments to get translation count if document has been processed
                if (doc.status !== 'uploaded') {
                    try {
                        const segments = await api.segments.list(doc.id)
                        segmentCount = segments.length
                        translatedCount = segments.filter(s => s.translated_text).length
                    } catch {
                        // Ignore segment fetch errors
                    }
                }

                // Map document status to job status
                let jobStatus = 'queued'
                if (doc.status === 'translated' || doc.status === 'approved' || doc.status === 'in_review') {
                    jobStatus = 'completed'
                } else if (doc.status === 'processing') {
                    jobStatus = 'processing'
                } else if (doc.status === 'uploaded') {
                    jobStatus = 'queued'
                }

                const progress = segmentCount > 0 ? Math.round((translatedCount / segmentCount) * 100) : 0

                return {
                    id: doc.id,
                    document_id: doc.id,
                    document_name: doc.name || 'Untitled Document',
                    file_type: doc.file_type || 'pdf',
                    target_language: doc.target_language || '',
                    source_language: doc.source_language || 'en',
                    status: jobStatus,
                    progress: jobStatus === 'completed' ? 100 : progress,
                    segment_count: segmentCount,
                    translated_count: translatedCount,
                    quality_status: doc.status === 'in_review' ? 'review_required' : 'passed',
                    confidence_score: doc.confidence_score,
                    score_breakdown: (doc as Document & { score_breakdown?: EnrichedJob["score_breakdown"] }).score_breakdown,
                    created_at: doc.created_at,
                    completed_at: doc.updated_at
                }
            }))

            // Sort by most recent first
            enrichedJobs.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
            setJobs(enrichedJobs)
        } catch (err) {
            console.error("Failed to fetch jobs:", err)
            setError(getErrMessage(err, "Failed to load jobs"))
            setJobs([])
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchJobs()
    }, [])

    // Filtered and searched jobs
    const filteredJobs = useMemo(() => {
        return jobs.filter(job => {
            const matchesSearch = searchQuery === "" ||
                job.document_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                job.target_language.toLowerCase().includes(searchQuery.toLowerCase())

            const matchesStatus = statusFilter === "all" || job.status === statusFilter

            return matchesSearch && matchesStatus
        })
    }, [jobs, searchQuery, statusFilter])

    // Stats
    const stats = useMemo(() => ({
        total: jobs.length,
        completed: jobs.filter(j => j.status === 'completed').length,
        processing: jobs.filter(j => j.status === 'processing').length,
        queued: jobs.filter(j => j.status === 'queued').length
    }), [jobs])

    const getStatusBadge = (status: string) => {
        const styles: Record<string, { bg: string; color: string; icon: React.ReactNode }> = {
            completed: { bg: "#dcfce7", color: "#166534", icon: <CheckCircle2 size={14} /> },
            processing: { bg: "#dbeafe", color: "#1e40af", icon: <Play size={14} /> },
            queued: { bg: "#f3f4f6", color: "#374151", icon: <Clock size={14} /> },
            failed: { bg: "#fef2f2", color: "#dc2626", icon: <AlertCircle size={14} /> }
        }
        const style = styles[status] || styles.queued
        return (
            <span style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.375rem",
                padding: "0.375rem 0.75rem",
                background: style.bg,
                color: style.color,
                borderRadius: "20px",
                fontSize: "0.8125rem",
                fontWeight: 500
            }}>
                {style.icon}
                {status.charAt(0).toUpperCase() + status.slice(1)}
            </span>
        )
    }

    const formatDate = (dateStr: string) => {
        const d = new Date(dateStr)
        return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
    }

    const formatTime = (dateStr: string) => {
        const d = new Date(dateStr)
        return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    }

    if (loading) {
        return (
            <div style={{
                padding: "4rem",
                textAlign: "center",
                minHeight: "60vh",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center"
            }}>
                <div style={{
                    width: "64px",
                    height: "64px",
                    background: "linear-gradient(135deg, #4285f4, #1a73e8)",
                    borderRadius: "16px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    marginBottom: "1.5rem"
                }}>
                    <RefreshCw size={28} style={{ color: "white", animation: "spin 1s linear infinite" }} />
                </div>
                <p style={{ color: "#5f6368", fontSize: "1rem" }}>Loading translation jobs...</p>
            </div>
        )
    }

    if (error) {
        return (
            <div style={{ padding: "2rem", maxWidth: "1400px", margin: "0 auto" }}>
                <div style={{
                    padding: "3rem 2rem",
                    textAlign: "center",
                    background: "white",
                    borderRadius: "12px",
                    border: "1px solid #fecaca"
                }}>
                    <div style={{
                        width: "64px",
                        height: "64px",
                        background: "#fef2f2",
                        borderRadius: "16px",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        margin: "0 auto 1.5rem"
                    }}>
                        <WifiOff size={28} style={{ color: "#dc2626" }} />
                    </div>
                    <h2 style={{ fontSize: "1.25rem", fontWeight: 500, margin: "0 0 0.5rem", color: "#202124" }}>
                        Unable to load jobs
                    </h2>
                    <p style={{ color: "#5f6368", margin: "0 0 1.5rem", maxWidth: "450px", marginLeft: "auto", marginRight: "auto" }}>
                        {error}
                    </p>
                    <button
                        onClick={fetchJobs}
                        style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "0.5rem",
                            padding: "0.75rem 1.5rem",
                            background: "#1a73e8",
                            color: "white",
                            border: "none",
                            borderRadius: "24px",
                            cursor: "pointer",
                            fontWeight: 500,
                            fontSize: "0.9375rem"
                        }}
                    >
                        <RefreshCw size={16} />
                        Retry
                    </button>
                </div>
            </div>
        )
    }

    return (
        <div style={{ padding: "2rem", maxWidth: "1400px", margin: "0 auto" }}>
            {/* Header */}
            <div style={{ marginBottom: "2rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1rem" }}>
                    <div>
                        <h1 style={{ fontSize: "1.75rem", fontWeight: 600, margin: "0 0 0.5rem", color: "#202124" }}>
                            Translation Jobs
                        </h1>
                        <p style={{ color: "#5f6368", margin: 0 }}>
                            Monitor and manage your translation pipeline
                        </p>
                    </div>
                    <div style={{ display: "flex", gap: "0.75rem" }}>
                        <button
                            onClick={fetchJobs}
                            style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "0.5rem",
                                padding: "0.625rem 1rem",
                                background: "white",
                                border: "1px solid #dadce0",
                                borderRadius: "8px",
                                cursor: "pointer",
                                fontSize: "0.875rem",
                                fontWeight: 500,
                                color: "#3c4043"
                            }}
                        >
                            <RefreshCw size={16} />
                            Refresh
                        </button>
                        <Link href="/workspace/upload" style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "0.5rem",
                            padding: "0.625rem 1.25rem",
                            background: "linear-gradient(135deg, #1e8e3e, #137333)",
                            color: "white",
                            borderRadius: "8px",
                            textDecoration: "none",
                            fontWeight: 500,
                            fontSize: "0.875rem"
                        }}>
                            <FileText size={16} />
                            New Translation
                        </Link>
                    </div>
                </div>

                {/* Stats Cards */}
                <div style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(4, 1fr)",
                    gap: "1rem",
                    marginBottom: "1.5rem"
                }}>
                    {/* ... (Keep existing stats cards code if same, assuming standard implementation) ... */}
                    {/* Re-implementing compact stats cards to ensure file completeness */}
                    <div className="bg-white rounded-xl p-5 border border-slate-200">
                        <div className="flex items-center gap-3 mb-2">
                            <div className="w-9 h-9 bg-blue-50 rounded-lg flex items-center justify-center">
                                <Languages size={18} className="text-blue-600" />
                            </div>
                            <span className="text-slate-500 text-sm">Total Jobs</span>
                        </div>
                        <div className="text-2xl font-semibold text-slate-900">{stats.total}</div>
                    </div>

                    <div className="bg-white rounded-xl p-5 border border-slate-200">
                        <div className="flex items-center gap-3 mb-2">
                            <div className="w-9 h-9 bg-green-50 rounded-lg flex items-center justify-center">
                                <CheckCircle2 size={18} className="text-green-600" />
                            </div>
                            <span className="text-slate-500 text-sm">Completed</span>
                        </div>
                        <div className="text-2xl font-semibold text-green-700">{stats.completed}</div>
                    </div>

                    <div className="bg-white rounded-xl p-5 border border-slate-200">
                        <div className="flex items-center gap-3 mb-2">
                            <div className="w-9 h-9 bg-blue-50 rounded-lg flex items-center justify-center">
                                <Zap size={18} className="text-blue-600" />
                            </div>
                            <span className="text-slate-500 text-sm">Processing</span>
                        </div>
                        <div className="text-2xl font-semibold text-blue-600">{stats.processing}</div>
                    </div>

                    <div className="bg-white rounded-xl p-5 border border-slate-200">
                        <div className="flex items-center gap-3 mb-2">
                            <div className="w-9 h-9 bg-slate-100 rounded-lg flex items-center justify-center">
                                <Clock size={18} className="text-slate-500" />
                            </div>
                            <span className="text-slate-500 text-sm">Queued</span>
                        </div>
                        <div className="text-2xl font-semibold text-slate-500">{stats.queued}</div>
                    </div>
                </div>
            </div>

            {/* Search and Filters */}
            <div style={{
                background: "white",
                borderRadius: "12px",
                border: "1px solid #e8eaed",
                marginBottom: "1rem"
            }}>
                <div style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "1rem",
                    padding: "1rem 1.5rem",
                    borderBottom: filteredJobs.length > 0 ? "1px solid #e8eaed" : "none"
                }}>
                    {/* Search */}
                    <div style={{
                        flex: 1,
                        display: "flex",
                        alignItems: "center",
                        gap: "0.75rem",
                        padding: "0.75rem 1rem",
                        background: "#f8f9fa",
                        borderRadius: "8px",
                        border: "1px solid transparent"
                    }}>
                        <Search size={18} style={{ color: "#5f6368" }} />
                        <input
                            type="text"
                            placeholder="Search by document name or language..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            style={{
                                flex: 1,
                                border: "none",
                                background: "transparent",
                                fontSize: "0.9375rem",
                                outline: "none",
                                color: "#202124"
                            }}
                        />
                    </div>

                    {/* Status Filter */}
                    <div style={{ display: "flex", gap: "0.5rem" }}>
                        {['all', 'completed', 'processing', 'queued'].map(status => (
                            <button
                                key={status}
                                onClick={() => setStatusFilter(status)}
                                style={{
                                    padding: "0.5rem 1rem",
                                    background: statusFilter === status ? "#e8f0fe" : "transparent",
                                    color: statusFilter === status ? "#1a73e8" : "#5f6368",
                                    border: "1px solid",
                                    borderColor: statusFilter === status ? "#1a73e8" : "#dadce0",
                                    borderRadius: "20px",
                                    cursor: "pointer",
                                    fontSize: "0.8125rem",
                                    fontWeight: 500,
                                    textTransform: "capitalize"
                                }}
                            >
                                {status === 'all' ? 'All Jobs' : status}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Jobs List */}
                {filteredJobs.length === 0 ? (
                    <div style={{
                        textAlign: "center",
                        padding: "4rem 2rem"
                    }}>
                        <div style={{
                            width: "64px",
                            height: "64px",
                            background: "linear-gradient(135deg, #4285f4, #1a73e8)",
                            borderRadius: "16px",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            margin: "0 auto 1.5rem"
                        }}>
                            <Languages size={28} style={{ color: "white" }} />
                        </div>
                        <h2 style={{ fontSize: "1.25rem", fontWeight: 500, margin: "0 0 0.5rem", color: "#202124" }}>
                            {searchQuery || statusFilter !== 'all' ? "No matching jobs found" : "No translation jobs yet"}
                        </h2>
                        <p style={{ color: "#5f6368", margin: "0 0 1.5rem", maxWidth: "400px", marginLeft: "auto", marginRight: "auto" }}>
                            {searchQuery || statusFilter !== 'all'
                                ? "Try adjusting your search or filters"
                                : "Upload a document and start a translation to see your jobs here."}
                        </p>
                        {!searchQuery && statusFilter === 'all' && (
                            <Link href="/workspace/upload" style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "0.5rem",
                                padding: "0.75rem 1.5rem",
                                background: "linear-gradient(135deg, #4285f4, #1a73e8)",
                                color: "white",
                                borderRadius: "24px",
                                textDecoration: "none",
                                fontWeight: 500,
                                fontSize: "0.9375rem"
                            }}>
                                <FileText size={18} />
                                Upload Document
                            </Link>
                        )}
                    </div>
                ) : (
                    <div>
                        {/* Table Header */}
                        <div style={{
                            display: "grid",
                            gridTemplateColumns: "2fr 120px 100px 120px 120px 150px 100px",
                            padding: "0.875rem 1.5rem",
                            background: "#fafbfc",
                            borderBottom: "1px solid #e8eaed",
                            fontSize: "0.75rem",
                            fontWeight: 600,
                            color: "#5f6368",
                            textTransform: "uppercase",
                            letterSpacing: "0.5px"
                        }}>
                            <span>Document</span>
                            <span>Target Language</span>
                            <span>Segments</span>
                            <span>Risk Score</span> {/* New Column */}
                            <span>Status</span>
                            <span>Created</span>
                            <span>Actions</span>
                        </div>

                        {/* Table Rows */}
                        {filteredJobs.map((job) => (
                            <div
                                key={job.id}
                                style={{
                                    display: "grid",
                                    gridTemplateColumns: "2fr 120px 100px 120px 120px 150px 100px",
                                    padding: "1rem 1.5rem",
                                    borderBottom: "1px solid #f0f0f0",
                                    alignItems: "center",
                                    transition: "background 0.15s",
                                    cursor: "pointer"
                                }}
                                onMouseEnter={(e) => e.currentTarget.style.background = "#f8f9fa"}
                                onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                            >
                                {/* Document Info */}
                                <div style={{ display: "flex", alignItems: "center", gap: "0.875rem" }}>
                                    <div style={{
                                        width: "40px",
                                        height: "40px",
                                        background: "#e8f0fe",
                                        borderRadius: "8px",
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center"
                                    }}>
                                        <FileText size={18} style={{ color: "#1a73e8" }} />
                                    </div>
                                    <div>
                                        <div style={{
                                            fontWeight: 500,
                                            color: "#202124",
                                            fontSize: "0.9375rem",
                                            marginBottom: "0.125rem"
                                        }}>
                                            {job.document_name}
                                        </div>
                                        <div style={{
                                            fontSize: "0.75rem",
                                            color: "#5f6368",
                                            textTransform: "uppercase"
                                        }}>
                                            {job.file_type || 'PDF'}
                                        </div>
                                    </div>
                                </div>

                                {/* Target Language */}
                                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                    <Target size={14} style={{ color: "#5f6368" }} />
                                    <span style={{ color: "#202124", fontWeight: 500 }}>
                                        {LANGUAGE_NAMES[job.target_language] || job.target_language || '—'}
                                    </span>
                                </div>

                                {/* Segments */}
                                <div>
                                    <div style={{ fontWeight: 500, color: "#202124" }}>
                                        {job.translated_count}/{job.segment_count}
                                    </div>
                                    <div style={{
                                        marginTop: "0.25rem",
                                        background: "#e8eaed",
                                        borderRadius: "4px",
                                        height: "4px",
                                        width: "60px"
                                    }}>
                                        <div style={{
                                            background: job.progress === 100 ? "#1e8e3e" : "#1a73e8",
                                            height: "100%",
                                            borderRadius: "4px",
                                            width: `${job.progress}%`,
                                            transition: "width 0.3s"
                                        }} />
                                    </div>
                                </div>

                                {/* Risk Score */}
                                <div>
                                    {job.confidence_score !== undefined && job.confidence_score !== null ? (
                                        <ConfidenceMeter score={job.confidence_score} breakdown={job.score_breakdown} />
                                    ) : (
                                        <span className="text-xs text-slate-400">—</span>
                                    )}
                                </div>

                                {/* Status */}
                                {getStatusBadge(job.status)}

                                {/* Date */}
                                <div>
                                    <div style={{ fontSize: "0.875rem", color: "#202124" }}>
                                        {formatDate(job.created_at)}
                                    </div>
                                    <div style={{ fontSize: "0.75rem", color: "#5f6368" }}>
                                        {formatTime(job.created_at)}
                                    </div>
                                </div>

                                {/* Actions */}
                                <div style={{ display: "flex", gap: "0.5rem" }}>
                                    <Link
                                        href={`/workspace/documents/${job.document_id}`}
                                        style={{
                                            display: "flex",
                                            alignItems: "center",
                                            justifyContent: "center",
                                            width: "32px",
                                            height: "32px",
                                            background: "#e8f0fe",
                                            borderRadius: "6px",
                                            color: "#1a73e8",
                                            textDecoration: "none"
                                        }}
                                        title="View Document"
                                    >
                                        <Eye size={16} />
                                    </Link>
                                    <Link
                                        href={`/workspace/documents/${job.document_id}`}
                                        style={{
                                            display: "flex",
                                            alignItems: "center",
                                            justifyContent: "center",
                                            width: "32px",
                                            height: "32px",
                                            background: "#f3f4f6",
                                            borderRadius: "6px",
                                            color: "#5f6368",
                                            textDecoration: "none"
                                        }}
                                        title="Open"
                                    >
                                        <ArrowUpRight size={16} />
                                    </Link>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Footer info */}
            {filteredJobs.length > 0 && (
                <div style={{
                    textAlign: "center",
                    padding: "1rem",
                    color: "#5f6368",
                    fontSize: "0.875rem"
                }}>
                    Showing {filteredJobs.length} of {jobs.length} jobs
                </div>
            )}

            <style jsx global>{`
                @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    )
}
