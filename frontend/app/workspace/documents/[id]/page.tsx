"use client"

import { useState, useEffect } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import {
    ArrowLeft, FileText, Globe, CheckCircle2, AlertTriangle, XCircle,
    Loader2, Download, Eye,
    AlertCircle, Info, Save, CheckSquare,
    Languages
} from "lucide-react"
import { api, Document, Segment } from "@/lib/api"
import { getErrMessage } from "@/lib/utils"
import { toast } from "sonner"

interface QualityScorecard {
    overall_score: number
    status: "PASSED" | "REVIEW_REQUIRED" | "BLOCKED"
    categories: {
        name: string
        score: number
        issues: number
    }[]
    total_segments: number
    translated_segments: number
    issue_segments: number
}

interface Defect {
    segment_id: string
    category: string
    severity: "critical" | "major" | "minor"
    message: string
    suggestion?: string
}

type ViewMode = "scorecard" | "segments" | "preview"

export default function DocumentReviewPage() {
    const params = useParams()
    const docId = params.id as string

    const [document, setDocument] = useState<Document | null>(null)
    const [segments, setSegments] = useState<Segment[]>([])
    const [loading, setLoading] = useState(true)
    // TMX-3604-doc-review-err: A3 — never substitute a default for a
    // failed fetch on a regulator-facing surface. Capture the actual
    // server message and surface it instead of "Document not found".
    const [error, setError] = useState<string | null>(null)
    const [viewMode, setViewMode] = useState<ViewMode>("scorecard")
    const [editingSegmentId, setEditingSegmentId] = useState<string | null>(null)
    const [editText, setEditText] = useState("")
    const [saving, setSaving] = useState(false)

    // Mock scorecard data (will come from API)
    const [scorecard, setScorecard] = useState<QualityScorecard>({
        overall_score: 94,
        status: "REVIEW_REQUIRED",
        categories: [
            { name: "Terminology", score: 100, issues: 0 },
            { name: "Negation Safety", score: 88, issues: 2 },
            { name: "Unit Conversion", score: 100, issues: 0 },
            { name: "Medical Accuracy", score: 96, issues: 1 },
        ],
        total_segments: 0,
        translated_segments: 0,
        issue_segments: 0
    })

    useEffect(() => {
        const fetchDocument = async () => {
            setLoading(true)
            try {
                const doc = await api.documents.get(docId)
                setDocument(doc)

                const segs = await api.segments.list(docId)
                setSegments(segs)

                // Calculate scorecard from real segment violations
                const translated = segs.filter((s: Segment) => s.translated_text)
                const allViolations = segs.flatMap((s: Segment) => s.gate_results?.violations || [])
                const withIssues = segs.filter((s: Segment) => (s.gate_results?.violations?.length || 0) > 0)

                // Count violations by category — Violation shape is inferred
                // from Segment.gate_results.violations (lib/api.ts).
                const terminologyIssues = allViolations.filter(v => v.category === 'terminology_violation').length
                const negationIssues = allViolations.filter(v => v.category === 'negation_error' || v.severity === 'critical').length
                const unitIssues = allViolations.filter(v => v.category === 'unit_mismatch').length
                const medicalIssues = allViolations.filter(v => v.category === 'medical_inaccuracy').length

                // Check for critical issues
                const criticalIssues = allViolations.filter(v => v.severity === 'critical').length

                // Determine status
                let status: "PASSED" | "REVIEW_REQUIRED" | "BLOCKED" = "PASSED"
                if (criticalIssues > 0) {
                    status = "BLOCKED"
                } else if (allViolations.length > 0) {
                    status = "REVIEW_REQUIRED"
                }

                setScorecard({
                    overall_score: segs.length > 0
                        ? Math.round((1 - withIssues.length / segs.length) * 100)
                        : 100,
                    status: status,
                    categories: [
                        { name: "Terminology", score: terminologyIssues === 0 ? 100 : Math.max(0, 100 - terminologyIssues * 10), issues: terminologyIssues },
                        { name: "Negation Safety", score: negationIssues === 0 ? 100 : Math.max(0, 100 - negationIssues * 15), issues: negationIssues },
                        { name: "Unit Conversion", score: unitIssues === 0 ? 100 : Math.max(0, 100 - unitIssues * 20), issues: unitIssues },
                        { name: "Medical Accuracy", score: medicalIssues === 0 ? 100 : Math.max(0, 100 - medicalIssues * 10), issues: medicalIssues },
                    ],
                    total_segments: segs.length,
                    translated_segments: translated.length,
                    issue_segments: withIssues.length
                })
            } catch (err) {
                setError(getErrMessage(err, "Failed to load document"))
                setDocument(null)
            } finally {
                setLoading(false)
            }
        }
        fetchDocument()
    }, [docId])

    // Get defects from segments
    const defects: Defect[] = segments.flatMap(seg => {
        const violations = seg.gate_results?.violations || []
        return violations.map(v => ({
            segment_id: seg.id,
            category: v.category || "Unknown",
            severity: (v.severity as Defect["severity"]) || "minor",
            message: v.message || "Issue detected",
            suggestion: v.suggestion
        }))
    })

    const criticalCount = defects.filter(d => d.severity === "critical").length
    const majorCount = defects.filter(d => d.severity === "major").length
    const minorCount = defects.filter(d => d.severity === "minor").length

    const handleSaveEdit = async (segmentId: string) => {
        setSaving(true)
        try {
            await api.segments.update(segmentId, editText, "HITL correction")
            // Refresh segments
            const segs = await api.segments.list(docId)
            setSegments(segs)
            setEditingSegmentId(null)
        } catch (err) {
            // TMX-3604-save-toast: HITL corrections are audit events
            // (A1) so a silent save failure leaves the audit chain
            // missing the attempt. Surface the real server message;
            // edit mode persists so the reviewer can retry.
            toast.error(getErrMessage(err, "Failed to save segment"))
        } finally {
            setSaving(false)
        }
    }

    const exportCSV = () => {
        const headers = ["Segment ID", "Order", "Source Text", "Translated Text", "Status", "Confidence", "Issues"]
        const rows = segments.map(seg => [
            seg.id,
            seg.order_index,
            `"${seg.source_text.replace(/"/g, '""')}"`,
            `"${(seg.translated_text || "").replace(/"/g, '""')}"`,
            seg.status,
            seg.confidence_score ? `${Math.round(seg.confidence_score * 100)}%` : "",
            seg.gate_results?.violations?.length || 0
        ])

        const csv = [headers.join(","), ...rows.map(r => r.join(","))].join("\n")
        const blob = new Blob([csv], { type: "text/csv" })
        const url = URL.createObjectURL(blob)
        const a = window.document.createElement("a")
        a.href = url
        a.download = `${document?.name || "translation"}_export.csv`
        a.click()
        URL.revokeObjectURL(url)
    }

    const getSeverityColor = (severity: string) => {
        switch (severity) {
            case "critical": return { bg: "#fef2f2", border: "#fecaca", text: "#dc2626", icon: <XCircle size={14} /> }
            case "major": return { bg: "#fff7ed", border: "#fed7aa", text: "#ea580c", icon: <AlertTriangle size={14} /> }
            default: return { bg: "#fefce8", border: "#fef08a", text: "#ca8a04", icon: <Info size={14} /> }
        }
    }

    if (loading) {
        return (
            <div style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                height: "100vh",
                background: "#f8f9fa"
            }}>
                <div style={{ textAlign: "center" }}>
                    <Loader2 size={40} style={{ color: "#1a73e8", animation: "spin 1s linear infinite" }} />
                    <p style={{ marginTop: "1rem", color: "#5f6368" }}>Loading document...</p>
                </div>
            </div>
        )
    }

    if (!document) {
        return (
            <div style={{ padding: "3rem", textAlign: "center" }}>
                {/* TMX-3604-doc-review-err: surface the real server message
                    when a fetch failed; fall through to the legitimate
                    "Document not found" only when the server returned
                    nothing (initial empty state, never reached in practice
                    since fetch always sets either doc or error). */}
                {error ? (
                    <>
                        <h2>Couldn&apos;t load document</h2>
                        <p style={{ color: "#5f6368", marginTop: "0.5rem", marginBottom: "1.5rem" }}>{error}</p>
                    </>
                ) : (
                    <h2>Document not found</h2>
                )}
                <Link href="/workspace">Back to Workspace</Link>
            </div>
        )
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
                    maxWidth: "1400px",
                    margin: "0 auto",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between"
                }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                        <Link href="/workspace" style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "0.5rem",
                            color: "#5f6368",
                            textDecoration: "none"
                        }}>
                            <ArrowLeft size={18} />
                        </Link>
                        <div style={{
                            width: "40px",
                            height: "40px",
                            background: "linear-gradient(135deg, #4285f4, #1a73e8)",
                            borderRadius: "10px",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center"
                        }}>
                            <FileText size={20} style={{ color: "white" }} />
                        </div>
                        <div>
                            <h1 style={{ fontSize: "1.125rem", fontWeight: 500, margin: 0 }}>
                                {document.name}
                            </h1>
                            <div style={{ fontSize: "0.8125rem", color: "#5f6368", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                <Globe size={12} />
                                {document.source_language || "en"} → {document.target_language || "de"}
                            </div>
                        </div>
                    </div>

                    {/* View Mode Tabs */}
                    <div style={{
                        display: "flex",
                        background: "#f0f0f0",
                        borderRadius: "8px",
                        padding: "4px"
                    }}>
                        {[
                            { id: "scorecard", label: "Quality Scorecard", icon: <CheckSquare size={16} /> },
                            { id: "segments", label: "Segments", icon: <Languages size={16} /> },
                            { id: "preview", label: "Preview", icon: <Eye size={16} /> },
                        ].map(tab => (
                            <button
                                key={tab.id}
                                onClick={() => setViewMode(tab.id as ViewMode)}
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "0.5rem",
                                    padding: "0.5rem 1rem",
                                    background: viewMode === tab.id ? "white" : "transparent",
                                    border: "none",
                                    borderRadius: "6px",
                                    fontSize: "0.875rem",
                                    fontWeight: 500,
                                    cursor: "pointer",
                                    color: viewMode === tab.id ? "#202124" : "#5f6368",
                                    boxShadow: viewMode === tab.id ? "0 1px 3px rgba(0,0,0,0.1)" : "none"
                                }}
                            >
                                {tab.icon}
                                {tab.label}
                            </button>
                        ))}
                    </div>

                    {/* Actions */}
                    <div style={{ display: "flex", gap: "0.75rem" }}>
                        <button
                            onClick={async () => {
                                try {
                                    const blob = await api.documents.downloadTranslated(docId)
                                    const url = URL.createObjectURL(blob)
                                    const a = window.document.createElement("a")
                                    const ext = document?.file_type === "txt" ? "txt" : "docx"
                                    a.href = url
                                    a.download = `${(document?.name || "translation").replace(/\.[^.]+$/, "")}_translated.${ext}`
                                    window.document.body.appendChild(a)
                                    a.click()
                                    a.remove()
                                    URL.revokeObjectURL(url)
                                } catch (err) {
                                    // TMX-3604-download-toast: same fix as
                                    // JobsView download — silent failure
                                    // looks like a popup blocker.
                                    toast.error(getErrMessage(err, "Download failed"))
                                }
                            }}
                            style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "0.5rem",
                                padding: "0.5rem 1rem",
                                background: "linear-gradient(135deg, #1a73e8, #1557b0)",
                                color: "white",
                                border: "none",
                                borderRadius: "8px",
                                fontSize: "0.875rem",
                                fontWeight: 500,
                                cursor: "pointer"
                            }}
                        >
                            <Download size={16} />
                            Download Translated
                        </button>
                        <button
                            onClick={exportCSV}
                            style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "0.5rem",
                                padding: "0.5rem 1rem",
                                background: "white",
                                border: "1px solid #dadce0",
                                borderRadius: "8px",
                                fontSize: "0.875rem",
                                cursor: "pointer"
                            }}
                        >
                            <Download size={16} />
                            Export CSV
                        </button>
                        <button style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "0.5rem",
                            padding: "0.5rem 1.25rem",
                            background: "linear-gradient(135deg, #1e8e3e, #188038)",
                            color: "white",
                            border: "none",
                            borderRadius: "8px",
                            fontSize: "0.875rem",
                            fontWeight: 500,
                            cursor: "pointer"
                        }}>
                            <CheckCircle2 size={16} />
                            Approve All
                        </button>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main style={{ maxWidth: "1400px", margin: "0 auto", padding: "2rem" }}>

                {/* Scorecard View */}
                {viewMode === "scorecard" && (
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: "1.5rem" }}>
                        {/* Left: Main Scorecard */}
                        <div>
                            {/* Overall Score Card */}
                            <div style={{
                                background: "white",
                                borderRadius: "16px",
                                border: "1px solid #e0e0e0",
                                padding: "2rem",
                                marginBottom: "1.5rem",
                                display: "flex",
                                alignItems: "center",
                                gap: "2rem"
                            }}>
                                <div style={{
                                    width: "140px",
                                    height: "140px",
                                    borderRadius: "70px",
                                    background: `conic-gradient(
                                        ${scorecard.overall_score >= 90 ? "#1e8e3e" : scorecard.overall_score >= 70 ? "#f9ab00" : "#dc2626"} ${scorecard.overall_score * 3.6}deg,
                                        #e5e5e5 0deg
                                    )`,
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center"
                                }}>
                                    <div style={{
                                        width: "110px",
                                        height: "110px",
                                        background: "white",
                                        borderRadius: "55px",
                                        display: "flex",
                                        flexDirection: "column",
                                        alignItems: "center",
                                        justifyContent: "center"
                                    }}>
                                        <span style={{
                                            fontSize: "2.5rem",
                                            fontWeight: 600,
                                            color: scorecard.overall_score >= 90 ? "#1e8e3e" : scorecard.overall_score >= 70 ? "#f9ab00" : "#dc2626"
                                        }}>
                                            {scorecard.overall_score}
                                        </span>
                                        <span style={{ fontSize: "0.75rem", color: "#5f6368" }}>Quality Score</span>
                                    </div>
                                </div>

                                <div style={{ flex: 1 }}>
                                    <div style={{
                                        display: "inline-flex",
                                        alignItems: "center",
                                        gap: "0.5rem",
                                        padding: "0.5rem 1rem",
                                        background: scorecard.status === "PASSED" ? "#e6f4ea" : scorecard.status === "BLOCKED" ? "#fef2f2" : "#fef7e0",
                                        borderRadius: "20px",
                                        marginBottom: "1rem"
                                    }}>
                                        {scorecard.status === "PASSED" ? (
                                            <CheckCircle2 size={16} style={{ color: "#1e8e3e" }} />
                                        ) : scorecard.status === "BLOCKED" ? (
                                            <XCircle size={16} style={{ color: "#dc2626" }} />
                                        ) : (
                                            <AlertTriangle size={16} style={{ color: "#f9ab00" }} />
                                        )}
                                        <span style={{
                                            fontWeight: 500,
                                            color: scorecard.status === "PASSED" ? "#1e8e3e" : scorecard.status === "BLOCKED" ? "#dc2626" : "#b45309"
                                        }}>
                                            {scorecard.status === "PASSED" ? "All Checks Passed" :
                                                scorecard.status === "BLOCKED" ? "Critical Issues Found" :
                                                    "Human Review Required"}
                                        </span>
                                    </div>

                                    <div style={{
                                        display: "grid",
                                        gridTemplateColumns: "repeat(3, 1fr)",
                                        gap: "1rem"
                                    }}>
                                        <div>
                                            <div style={{ fontSize: "1.5rem", fontWeight: 600, color: "#202124" }}>
                                                {scorecard.translated_segments}/{scorecard.total_segments}
                                            </div>
                                            <div style={{ fontSize: "0.8125rem", color: "#5f6368" }}>Segments Translated</div>
                                        </div>
                                        <div>
                                            <div style={{ fontSize: "1.5rem", fontWeight: 600, color: criticalCount > 0 ? "#dc2626" : "#1e8e3e" }}>
                                                {criticalCount}
                                            </div>
                                            <div style={{ fontSize: "0.8125rem", color: "#5f6368" }}>Critical Issues</div>
                                        </div>
                                        <div>
                                            <div style={{ fontSize: "1.5rem", fontWeight: 600, color: "#f9ab00" }}>
                                                {majorCount + minorCount}
                                            </div>
                                            <div style={{ fontSize: "0.8125rem", color: "#5f6368" }}>Warnings</div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Category Breakdown */}
                            <div style={{
                                background: "white",
                                borderRadius: "16px",
                                border: "1px solid #e0e0e0",
                                padding: "1.5rem"
                            }}>
                                <h3 style={{ fontSize: "1rem", fontWeight: 500, margin: "0 0 1rem" }}>
                                    Quality Categories
                                </h3>
                                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                                    {scorecard.categories.map((cat, idx) => (
                                        <div key={idx} style={{
                                            display: "flex",
                                            alignItems: "center",
                                            gap: "1rem"
                                        }}>
                                            <div style={{ width: "140px", fontSize: "0.9375rem", color: "#202124" }}>
                                                {cat.name}
                                            </div>
                                            <div style={{ flex: 1, height: "8px", background: "#e5e5e5", borderRadius: "4px", overflow: "hidden" }}>
                                                <div style={{
                                                    height: "100%",
                                                    width: `${cat.score}%`,
                                                    background: cat.score >= 90 ? "#1e8e3e" : cat.score >= 70 ? "#f9ab00" : "#dc2626",
                                                    borderRadius: "4px"
                                                }} />
                                            </div>
                                            <div style={{
                                                width: "50px",
                                                fontSize: "0.875rem",
                                                fontWeight: 500,
                                                color: cat.score >= 90 ? "#1e8e3e" : cat.score >= 70 ? "#f9ab00" : "#dc2626"
                                            }}>
                                                {cat.score}%
                                            </div>
                                            {cat.issues > 0 && (
                                                <span style={{
                                                    padding: "0.25rem 0.5rem",
                                                    background: "#fef2f2",
                                                    borderRadius: "12px",
                                                    fontSize: "0.75rem",
                                                    color: "#dc2626",
                                                    fontWeight: 500
                                                }}>
                                                    {cat.issues} issues
                                                </span>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>

                        {/* Right: Issues Panel */}
                        <div style={{
                            background: "white",
                            borderRadius: "16px",
                            border: "1px solid #e0e0e0",
                            overflow: "hidden"
                        }}>
                            <div style={{
                                padding: "1rem 1.25rem",
                                borderBottom: "1px solid #e0e0e0",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between"
                            }}>
                                <h3 style={{ fontSize: "1rem", fontWeight: 500, margin: 0 }}>
                                    Issues Requiring Review
                                </h3>
                                <span style={{
                                    padding: "0.25rem 0.75rem",
                                    background: "#fef2f2",
                                    borderRadius: "12px",
                                    fontSize: "0.75rem",
                                    color: "#dc2626",
                                    fontWeight: 500
                                }}>
                                    {defects.length} total
                                </span>
                            </div>

                            <div style={{ maxHeight: "500px", overflowY: "auto" }}>
                                {defects.length === 0 ? (
                                    <div style={{ padding: "3rem", textAlign: "center", color: "#5f6368" }}>
                                        <CheckCircle2 size={40} style={{ color: "#1e8e3e", marginBottom: "1rem" }} />
                                        <p>No issues found!</p>
                                    </div>
                                ) : (
                                    defects.map((defect, idx) => {
                                        const colors = getSeverityColor(defect.severity)
                                        return (
                                            <div key={idx} style={{
                                                padding: "1rem 1.25rem",
                                                borderBottom: "1px solid #f0f0f0",
                                                background: colors.bg
                                            }}>
                                                <div style={{
                                                    display: "flex",
                                                    alignItems: "center",
                                                    gap: "0.5rem",
                                                    marginBottom: "0.5rem"
                                                }}>
                                                    <span style={{ color: colors.text }}>{colors.icon}</span>
                                                    <span style={{
                                                        fontSize: "0.75rem",
                                                        fontWeight: 600,
                                                        color: colors.text,
                                                        textTransform: "uppercase"
                                                    }}>
                                                        {defect.severity}
                                                    </span>
                                                    <span style={{
                                                        fontSize: "0.75rem",
                                                        color: "#5f6368",
                                                        marginLeft: "auto"
                                                    }}>
                                                        {defect.category}
                                                    </span>
                                                </div>
                                                <p style={{
                                                    margin: "0 0 0.5rem",
                                                    fontSize: "0.875rem",
                                                    color: "#202124"
                                                }}>
                                                    {defect.message}
                                                </p>
                                                {defect.suggestion && (
                                                    <div style={{
                                                        padding: "0.5rem 0.75rem",
                                                        background: "white",
                                                        borderRadius: "6px",
                                                        border: `1px solid ${colors.border}`,
                                                        fontSize: "0.8125rem"
                                                    }}>
                                                        <strong>Suggestion:</strong> {defect.suggestion}
                                                    </div>
                                                )}
                                                <button
                                                    onClick={() => {
                                                        setViewMode("segments")
                                                        // Scroll to segment
                                                    }}
                                                    style={{
                                                        marginTop: "0.5rem",
                                                        padding: "0.375rem 0.75rem",
                                                        background: "white",
                                                        border: "1px solid #dadce0",
                                                        borderRadius: "6px",
                                                        fontSize: "0.75rem",
                                                        cursor: "pointer"
                                                    }}
                                                >
                                                    Go to Segment →
                                                </button>
                                            </div>
                                        )
                                    })
                                )}
                            </div>
                        </div>
                    </div>
                )}

                {/* Segments View */}
                {viewMode === "segments" && (
                    <div style={{
                        background: "white",
                        borderRadius: "16px",
                        border: "1px solid #e0e0e0",
                        overflow: "hidden"
                    }}>
                        {/* TMX-UX-SEG-COUNT: an auditor needs the review scope
                            up front — how many segments exist, how many are
                            translated, and how many still need a human. */}
                        <div style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            gap: "1rem",
                            flexWrap: "wrap",
                            padding: "0.625rem 1.25rem",
                            background: "white",
                            borderBottom: "1px solid #e0e0e0",
                            fontSize: "0.8125rem",
                            color: "#5f6368",
                            fontWeight: 500
                        }}>
                            <span>{segments.length} segment{segments.length === 1 ? "" : "s"}</span>
                            <span>
                                {segments.filter(s => s.translated_text).length} translated
                                {" · "}
                                {segments.filter(s => (s.gate_results?.violations?.length || 0) > 0).length} need review
                            </span>
                        </div>
                        <div style={{
                            display: "grid",
                            gridTemplateColumns: "60px 1fr 1fr 100px",
                            padding: "0.75rem 1.25rem",
                            background: "#f8f9fa",
                            borderBottom: "1px solid #e0e0e0",
                            fontSize: "0.75rem",
                            fontWeight: 600,
                            color: "#5f6368",
                            textTransform: "uppercase"
                        }}>
                            <span>#</span>
                            <span>Source ({document.source_language || "EN"})</span>
                            <span>Target ({document.target_language || "DE"})</span>
                            <span>Status</span>
                        </div>

                        {segments.map((seg, idx) => {
                            const hasIssues = (seg.gate_results?.violations?.length || 0) > 0
                            const isEditing = editingSegmentId === seg.id

                            return (
                                <div key={seg.id} style={{
                                    display: "grid",
                                    gridTemplateColumns: "60px 1fr 1fr 100px",
                                    padding: "1rem 1.25rem",
                                    borderBottom: "1px solid #f0f0f0",
                                    background: hasIssues ? "#fffbeb" : "white",
                                    alignItems: "start"
                                }}>
                                    <span style={{ fontSize: "0.8125rem", color: "#80868b", fontWeight: 500 }}>
                                        {idx + 1}
                                    </span>
                                    <div style={{ paddingRight: "1rem" }}>
                                        <p style={{ margin: 0, fontSize: "0.9375rem", lineHeight: 1.6 }}>
                                            {seg.source_text}
                                        </p>
                                    </div>
                                    <div style={{ paddingRight: "1rem" }}>
                                        {isEditing ? (
                                            <div>
                                                <textarea
                                                    value={editText}
                                                    onChange={(e) => setEditText(e.target.value)}
                                                    style={{
                                                        width: "100%",
                                                        minHeight: "80px",
                                                        padding: "0.75rem",
                                                        border: "2px solid #1a73e8",
                                                        borderRadius: "8px",
                                                        fontSize: "0.9375rem",
                                                        lineHeight: 1.6,
                                                        fontFamily: "inherit",
                                                        resize: "vertical"
                                                    }}
                                                />
                                                <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
                                                    <button
                                                        onClick={() => handleSaveEdit(seg.id)}
                                                        disabled={saving}
                                                        style={{
                                                            display: "flex",
                                                            alignItems: "center",
                                                            gap: "0.375rem",
                                                            padding: "0.375rem 0.75rem",
                                                            background: "#1a73e8",
                                                            color: "white",
                                                            border: "none",
                                                            borderRadius: "6px",
                                                            fontSize: "0.8125rem",
                                                            cursor: "pointer"
                                                        }}
                                                    >
                                                        {saving ? <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} /> : <Save size={12} />}
                                                        Save
                                                    </button>
                                                    <button
                                                        onClick={() => setEditingSegmentId(null)}
                                                        style={{
                                                            padding: "0.375rem 0.75rem",
                                                            background: "white",
                                                            border: "1px solid #dadce0",
                                                            borderRadius: "6px",
                                                            fontSize: "0.8125rem",
                                                            cursor: "pointer"
                                                        }}
                                                    >
                                                        Cancel
                                                    </button>
                                                </div>
                                            </div>
                                        ) : (
                                            <div
                                                onClick={() => {
                                                    setEditingSegmentId(seg.id)
                                                    setEditText(seg.translated_text || "")
                                                }}
                                                style={{ cursor: "pointer" }}
                                            >
                                                <p style={{
                                                    margin: 0,
                                                    fontSize: "0.9375rem",
                                                    lineHeight: 1.6,
                                                    color: seg.translated_text ? "#202124" : "#9aa0a6",
                                                    fontStyle: seg.translated_text ? "normal" : "italic"
                                                }}>
                                                    {seg.translated_text || "Click to add translation..."}
                                                </p>
                                                {seg.confidence_score && (
                                                    <div style={{
                                                        display: "flex",
                                                        alignItems: "center",
                                                        gap: "0.5rem",
                                                        marginTop: "0.5rem"
                                                    }}>
                                                        <div style={{
                                                            width: "60px",
                                                            height: "4px",
                                                            background: "#e5e5e5",
                                                            borderRadius: "2px",
                                                            overflow: "hidden"
                                                        }}>
                                                            <div style={{
                                                                height: "100%",
                                                                width: `${seg.confidence_score * 100}%`,
                                                                background: seg.confidence_score > 0.9 ? "#1e8e3e" : "#f9ab00"
                                                            }} />
                                                        </div>
                                                        <span style={{
                                                            fontSize: "0.75rem",
                                                            color: seg.confidence_score > 0.9 ? "#1e8e3e" : "#f9ab00"
                                                        }}>
                                                            {Math.round(seg.confidence_score * 100)}%
                                                        </span>
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                    <div>
                                        {hasIssues ? (
                                            <span style={{
                                                display: "inline-flex",
                                                alignItems: "center",
                                                gap: "0.25rem",
                                                padding: "0.25rem 0.5rem",
                                                background: "#fef2f2",
                                                color: "#dc2626",
                                                borderRadius: "12px",
                                                fontSize: "0.75rem",
                                                fontWeight: 500
                                            }}>
                                                <AlertCircle size={12} />
                                                {seg.gate_results?.violations?.length} issues
                                            </span>
                                        ) : seg.translated_text ? (
                                            <span style={{
                                                display: "inline-flex",
                                                alignItems: "center",
                                                gap: "0.25rem",
                                                padding: "0.25rem 0.5rem",
                                                background: "#e6f4ea",
                                                color: "#1e8e3e",
                                                borderRadius: "12px",
                                                fontSize: "0.75rem",
                                                fontWeight: 500
                                            }}>
                                                <CheckCircle2 size={12} />
                                                OK
                                            </span>
                                        ) : (
                                            <span style={{
                                                padding: "0.25rem 0.5rem",
                                                background: "#f3f4f6",
                                                color: "#6b7280",
                                                borderRadius: "12px",
                                                fontSize: "0.75rem"
                                            }}>
                                                Pending
                                            </span>
                                        )}
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                )}

                {/* Preview View */}
                {viewMode === "preview" && (
                    <div style={{
                        background: "white",
                        borderRadius: "16px",
                        border: "1px solid #e0e0e0",
                        padding: "3rem",
                        maxWidth: "800px",
                        margin: "0 auto",
                        boxShadow: "0 4px 20px rgba(0,0,0,0.08)"
                    }}>
                        <div style={{
                            textAlign: "center",
                            marginBottom: "2rem",
                            paddingBottom: "2rem",
                            borderBottom: "1px solid #e0e0e0"
                        }}>
                            <h1 style={{ fontSize: "1.5rem", fontWeight: 600, margin: "0 0 0.5rem" }}>
                                {document.name}
                            </h1>
                            <p style={{ color: "#5f6368", margin: 0 }}>
                                Translated to {document.target_language === "de" ? "German" : document.target_language || "German"}
                            </p>
                        </div>

                        <div style={{ fontSize: "1rem", lineHeight: 1.8, color: "#202124" }}>
                            {segments.map((seg) => (
                                <p key={seg.id} style={{
                                    marginBottom: "1rem",
                                    padding: seg.gate_results?.violations?.length ? "0.5rem" : "0",
                                    background: seg.gate_results?.violations?.length ? "#fffbeb" : "transparent",
                                    borderLeft: seg.gate_results?.violations?.length ? "3px solid #f9ab00" : "none"
                                }}>
                                    {seg.translated_text || (
                                        <span style={{ color: "#9aa0a6", fontStyle: "italic" }}>
                                            [{seg.source_text}]
                                        </span>
                                    )}
                                </p>
                            ))}
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
