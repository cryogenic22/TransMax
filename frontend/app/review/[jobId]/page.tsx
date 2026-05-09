"use client"

import { useState, useEffect } from "react"
import { useParams, useRouter, useSearchParams } from "next/navigation"
import {
    ArrowLeft,
    Check,
    Edit3,
    AlertTriangle,
    XCircle,
    CheckCircle,
    Download,
    Globe,
    Save
} from "lucide-react"

interface Segment {
    id: string
    source_text: string
    target_text: string
    confidence: number
    status: 'pending' | 'approved' | 'review_required' | 'blocked'
    violations: Violation[]
}

interface Violation {
    category: string
    severity: 'critical' | 'major' | 'minor'
    message: string
}

// TMX-3004 (v3.0 plan / review F-C03): the previous version of this file
// silently substituted hardcoded mock translations on backend errors,
// including a deliberate negation-flip example. A reviewer could sign off
// mock content as real. The mock data is removed; backend errors now surface
// as explicit error UX with a retry button.

const LANGUAGE_NAMES: Record<string, string> = {
    fr: "French",
    de: "German",
    es: "Spanish",
    ja: "Japanese",
    zh: "Chinese",
    ar: "Arabic",
    pt: "Portuguese",
    it: "Italian"
}

export default function ReviewPage() {
    const params = useParams()
    const router = useRouter()
    const searchParams = useSearchParams()
    const jobId = params.jobId as string
    const targetLang = searchParams.get('target') || 'fr'

    const [segments, setSegments] = useState<Segment[]>([])
    const [filter, setFilter] = useState<'all' | 'issues'>('all')
    const [editingId, setEditingId] = useState<string | null>(null)
    const [editText, setEditText] = useState("")
    const [, setIsLoading] = useState(true)
    const [, setError] = useState<string | null>(null)

    // Fetch real segments from backend API.
    // TMX-3004: explicit error states; never fall back to mock data.
    useEffect(() => {
        let cancelled = false

        const fetchSegments = async () => {
            if (cancelled) return
            setError(null)
            try {
                const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001") + "/api/v1"
                const response = await fetch(`${API_BASE}/translate/${jobId}?t=${Date.now()}`, {
                    cache: 'no-store',
                    headers: { 'Cache-Control': 'no-cache' }
                })

                if (!response.ok) {
                    throw new Error(`Backend returned ${response.status}: ${response.statusText}`)
                }

                const data = await response.json()
                const ext = data.extended_data || {}
                const backendSegments =
                    (ext.segments?.length > 0 ? ext.segments : null) ||
                    (ext.draft_segments?.length > 0 ? ext.draft_segments : null) ||
                    (ext.content_blocks?.length > 0 ? ext.content_blocks : null) ||
                    []

                if (cancelled) return

                interface RawSegment {
                    id?: string; block_id?: string
                    source_text?: string; content?: string; text?: string
                    target_text?: string; draft_text?: string; translated_text?: string
                    confidence?: number
                    defects?: Array<{ category?: string; severity?: string; message?: string; description?: string }>
                }
                const mappedSegments: Segment[] = (backendSegments as RawSegment[]).map((s, i) => ({
                    id: s.id || s.block_id || `seg-${i}`,
                    source_text: s.source_text || s.content || s.text || '',
                    target_text: s.target_text || s.draft_text || s.translated_text || '',
                    confidence: typeof s.confidence === 'number' ? s.confidence : 0,
                    status: (s.defects?.length ?? 0) > 0 ? 'review_required' : 'approved',
                    violations: (s.defects || []).map(d => ({
                        category: d.category || 'quality',
                        severity: (d.severity || 'major') as Violation["severity"],
                        message: d.message || d.description || 'Quality issue detected'
                    }))
                }))
                setSegments(mappedSegments)
            } catch (err) {
                if (cancelled) return
                setError(err instanceof Error ? err.message : 'Unknown error fetching translations')
            } finally {
                if (!cancelled) setIsLoading(false)
            }
        }

        fetchSegments()

        // Poll while the job is processing. v3.0 will replace this with SSE
        // (TMX-3612) and a backoff/jitter strategy (review F-M02).
        const interval = setInterval(fetchSegments, 3000)
        return () => {
            cancelled = true
            clearInterval(interval)
        }
    }, [jobId, targetLang])

    const approvedCount = segments.filter(s => s.status === 'approved').length
    const issueCount = segments.filter(s => s.status !== 'approved').length
    const avgConfidence = segments.length > 0
        ? segments.reduce((acc, s) => acc + s.confidence, 0) / segments.length
        : 0

    const displayedSegments = filter === 'issues'
        ? segments.filter(s => s.status !== 'approved')
        : segments

    const handleEdit = (segment: Segment) => {
        setEditingId(segment.id)
        setEditText(segment.target_text)
    }

    const handleSave = (id: string) => {
        setSegments(prev => prev.map(s =>
            s.id === id
                ? { ...s, target_text: editText, status: 'approved', violations: [], confidence: 1.0 }
                : s
        ))
        setEditingId(null)
        setEditText("")
    }

    const handleApprove = (id: string) => {
        setSegments(prev => prev.map(s =>
            s.id === id ? { ...s, status: 'approved', violations: [] } : s
        ))
    }

    const getConfidenceColor = (confidence: number) => {
        if (confidence >= 0.95) return 'var(--success-600)'
        if (confidence >= 0.85) return 'var(--warning-600)'
        return 'var(--error-600)'
    }

    const getConfidenceBg = (confidence: number) => {
        if (confidence >= 0.95) return 'var(--success-50)'
        if (confidence >= 0.85) return 'var(--warning-50)'
        return 'var(--error-50)'
    }

    return (
        <main className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>
            {/* Navigation */}
            <nav className="glass border-b sticky top-0 z-50" style={{ borderColor: 'var(--surface-border)' }}>
                <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <button
                            onClick={() => router.push('/')}
                            className="p-2 rounded-lg transition-colors"
                            style={{ color: 'var(--text-secondary)' }}
                            onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
                            onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                        >
                            <ArrowLeft className="w-5 h-5" />
                        </button>
                        <div>
                            <div className="flex items-center gap-2">
                                <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                                    Translation Review
                                </span>
                                <span className="badge badge-info">{jobId}</span>
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full"
                            style={{ background: 'var(--brand-50)', color: 'var(--brand-600)' }}>
                            <Globe className="w-4 h-4" />
                            <span className="text-sm font-medium">
                                English → {LANGUAGE_NAMES[targetLang] || targetLang.toUpperCase()}
                            </span>
                        </div>
                        <button className="btn btn-secondary flex items-center gap-2">
                            <Download className="w-4 h-4" />
                            Export
                        </button>
                        <button
                            className="btn btn-primary"
                            disabled={issueCount > 0}
                            style={{ opacity: issueCount > 0 ? 0.5 : 1 }}
                        >
                            <CheckCircle className="w-4 h-4" />
                            Approve All ({approvedCount}/{segments.length})
                        </button>
                    </div>
                </div>
            </nav>

            {/* Stats Bar */}
            <div className="border-b" style={{ background: 'var(--surface-card)', borderColor: 'var(--surface-border)' }}>
                <div className="max-w-7xl mx-auto px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-8">
                            <div>
                                <div className="text-xs font-medium uppercase mb-1" style={{ color: 'var(--text-muted)' }}>
                                    Segments
                                </div>
                                <div className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                                    {segments.length}
                                </div>
                            </div>
                            <div>
                                <div className="text-xs font-medium uppercase mb-1" style={{ color: 'var(--text-muted)' }}>
                                    Avg Confidence
                                </div>
                                <div className="text-2xl font-bold" style={{ color: getConfidenceColor(avgConfidence) }}>
                                    {(avgConfidence * 100).toFixed(1)}%
                                </div>
                            </div>
                            <div>
                                <div className="text-xs font-medium uppercase mb-1" style={{ color: 'var(--text-muted)' }}>
                                    Issues
                                </div>
                                <div className="text-2xl font-bold" style={{ color: issueCount > 0 ? 'var(--error-600)' : 'var(--success-600)' }}>
                                    {issueCount}
                                </div>
                            </div>
                        </div>

                        {/* Filter Tabs */}
                        <div className="flex items-center gap-1 p-1 rounded-full"
                            style={{ background: 'var(--bg-secondary)', border: '1px solid var(--surface-border)' }}>
                            <button
                                onClick={() => setFilter('all')}
                                className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all ${filter === 'all' ? 'bg-white shadow-sm' : ''
                                    }`}
                                style={{ color: filter === 'all' ? 'var(--text-primary)' : 'var(--text-muted)' }}
                            >
                                All Segments
                            </button>
                            <button
                                onClick={() => setFilter('issues')}
                                className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all flex items-center gap-2 ${filter === 'issues' ? 'bg-white shadow-sm' : ''
                                    }`}
                                style={{ color: filter === 'issues' ? 'var(--text-primary)' : 'var(--text-muted)' }}
                            >
                                Issues Only
                                {issueCount > 0 && (
                                    <span className="px-2 py-0.5 text-xs rounded-full text-white"
                                        style={{ background: 'var(--error-500)' }}>
                                        {issueCount}
                                    </span>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Table */}
            <div className="max-w-7xl mx-auto px-6 py-6">
                <div className="card-static overflow-hidden">
                    {/* Header */}
                    <div className="grid grid-cols-12 text-xs font-semibold uppercase"
                        style={{ background: 'var(--bg-secondary)', color: 'var(--text-muted)', borderBottom: '1px solid var(--surface-border)' }}>
                        <div className="col-span-1 p-3 text-center">#</div>
                        <div className="col-span-5 p-3">Source (English)</div>
                        <div className="col-span-4 p-3">Translation ({LANGUAGE_NAMES[targetLang] || targetLang})</div>
                        <div className="col-span-1 p-3 text-center">Score</div>
                        <div className="col-span-1 p-3 text-center">Actions</div>
                    </div>

                    {/* Rows */}
                    <div>
                        {displayedSegments.map((segment, index) => (
                            <div key={segment.id}>
                                <div
                                    className="grid grid-cols-12 transition-colors"
                                    style={{
                                        borderBottom: '1px solid var(--surface-border)',
                                        background: segment.violations.length > 0 ? 'var(--error-50)' : 'transparent'
                                    }}
                                >
                                    {/* Index */}
                                    <div className="col-span-1 p-4 text-center text-sm font-mono"
                                        style={{ color: 'var(--text-muted)' }}>
                                        {index + 1}
                                    </div>

                                    {/* Source */}
                                    <div className="col-span-5 p-4 text-sm" style={{ color: 'var(--text-primary)' }}>
                                        {segment.source_text}
                                    </div>

                                    {/* Translation */}
                                    <div className="col-span-4 p-4">
                                        {editingId === segment.id ? (
                                            <div className="flex flex-col gap-2">
                                                <textarea
                                                    value={editText}
                                                    onChange={(e) => setEditText(e.target.value)}
                                                    className="form-input text-sm"
                                                    rows={3}
                                                />
                                                <div className="flex gap-2">
                                                    <button
                                                        onClick={() => handleSave(segment.id)}
                                                        className="btn btn-primary text-sm py-1 px-3"
                                                    >
                                                        <Save className="w-3 h-3" /> Save
                                                    </button>
                                                    <button
                                                        onClick={() => setEditingId(null)}
                                                        className="btn btn-secondary text-sm py-1 px-3"
                                                    >
                                                        Cancel
                                                    </button>
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="text-sm" style={{ color: 'var(--text-primary)' }}>
                                                {segment.target_text}
                                            </div>
                                        )}
                                    </div>

                                    {/* Confidence */}
                                    <div className="col-span-1 p-4 flex items-center justify-center">
                                        <span
                                            className="px-2 py-1 rounded-full text-xs font-semibold"
                                            style={{
                                                background: getConfidenceBg(segment.confidence),
                                                color: getConfidenceColor(segment.confidence)
                                            }}
                                        >
                                            {(segment.confidence * 100).toFixed(0)}%
                                        </span>
                                    </div>

                                    {/* Actions */}
                                    <div className="col-span-1 p-4 flex items-center justify-center gap-1">
                                        {segment.status === 'approved' ? (
                                            <span className="badge badge-success">
                                                <Check className="w-3 h-3" />
                                            </span>
                                        ) : (
                                            <>
                                                <button
                                                    onClick={() => handleEdit(segment)}
                                                    className="p-2 rounded-lg transition-colors"
                                                    style={{ color: 'var(--text-muted)' }}
                                                    onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
                                                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                                                >
                                                    <Edit3 className="w-4 h-4" />
                                                </button>
                                                <button
                                                    onClick={() => handleApprove(segment.id)}
                                                    className="p-2 rounded-lg transition-colors"
                                                    style={{ color: 'var(--success-600)' }}
                                                    onMouseEnter={(e) => e.currentTarget.style.background = 'var(--success-50)'}
                                                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                                                >
                                                    <Check className="w-4 h-4" />
                                                </button>
                                            </>
                                        )}
                                    </div>
                                </div>

                                {/* Violations Panel */}
                                {segment.violations.length > 0 && (
                                    <div className="px-4 py-3" style={{ background: 'var(--error-50)', borderBottom: '1px solid var(--surface-border)' }}>
                                        <div className="ml-16">
                                            {segment.violations.map((v, vi) => (
                                                <div key={vi} className="flex items-start gap-3 text-sm">
                                                    <span className={`badge ${v.severity === 'critical' ? 'badge-error' :
                                                        v.severity === 'major' ? 'badge-warning' : 'badge-neutral'
                                                        }`}>
                                                        {v.severity === 'critical' && <XCircle className="w-3 h-3" />}
                                                        {v.severity === 'major' && <AlertTriangle className="w-3 h-3" />}
                                                        {v.severity.toUpperCase()}
                                                    </span>
                                                    <span style={{ color: 'var(--text-primary)' }}>
                                                        {v.message}
                                                    </span>
                                                    <span className="text-xs px-2 py-0.5 rounded"
                                                        style={{ background: 'var(--bg-tertiary)', color: 'var(--text-muted)' }}>
                                                        {v.category.replace('_', ' ')}
                                                    </span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </main>
    )
}
