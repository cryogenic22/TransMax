"use client"

import { useState, useEffect } from "react"
import { History, User, FileText, Edit3, RefreshCw, Clock, Activity } from "lucide-react"
import { api, AuditLog } from "@/lib/api"

export default function AuditPage() {
    const [logs, setLogs] = useState<AuditLog[]>([])
    const [loading, setLoading] = useState(true)

    const fetchLogs = async () => {
        setLoading(true)
        try {
            const data = await api.audit.list({ limit: 50 })
            setLogs(data)
        } catch {
            setLogs([])
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchLogs()
    }, [])

    const getActionIcon = (action: string) => {
        if (action.toLowerCase().includes("edit")) return <Edit3 size={14} />
        if (action.toLowerCase().includes("upload") || action.toLowerCase().includes("create")) return <FileText size={14} />
        if (action.toLowerCase().includes("translat")) return <Activity size={14} />
        return <History size={14} />
    }

    const formatTime = (dateStr: string) => {
        const date = new Date(dateStr)
        const now = new Date()
        const diff = now.getTime() - date.getTime()

        if (diff < 60000) return "Just now"
        if (diff < 3600000) return `${Math.floor(diff / 60000)} min ago`
        if (diff < 86400000) return `${Math.floor(diff / 3600000)} hours ago`
        return date.toLocaleDateString()
    }

    if (loading) {
        return (
            <div style={{ padding: "2rem", textAlign: "center" }}>
                <RefreshCw size={24} style={{ animation: "spin 1s linear infinite", color: "#666" }} />
                <p style={{ marginTop: "1rem", color: "#666" }}>Loading activity...</p>
            </div>
        )
    }

    return (
        <div style={{ padding: "2rem", maxWidth: "1000px", margin: "0 auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
                <h1 style={{ fontSize: "1.5rem", fontWeight: 500, margin: 0 }}>Audit Log</h1>
                <button
                    onClick={fetchLogs}
                    style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.5rem",
                        padding: "0.5rem 1rem",
                        background: "white",
                        border: "1px solid #e5e5e5",
                        borderRadius: "8px",
                        cursor: "pointer",
                        fontSize: "0.875rem"
                    }}
                >
                    <RefreshCw size={14} />
                    Refresh
                </button>
            </div>

            {logs.length === 0 ? (
                /* Empty State */
                <div style={{
                    textAlign: "center",
                    padding: "4rem 2rem",
                    background: "#fafafa",
                    borderRadius: "16px",
                    border: "1px solid #e5e5e5"
                }}>
                    <div style={{
                        width: "64px",
                        height: "64px",
                        background: "#f0f0f0",
                        borderRadius: "16px",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        margin: "0 auto 1.5rem"
                    }}>
                        <Clock size={28} style={{ color: "#666" }} />
                    </div>
                    <h2 style={{ fontSize: "1.25rem", fontWeight: 500, margin: "0 0 0.5rem" }}>
                        No activity yet
                    </h2>
                    <p style={{ color: "#666", margin: 0, maxWidth: "400px", marginLeft: "auto", marginRight: "auto" }}>
                        Activity will appear here as you upload documents, run translations, and make edits.
                    </p>
                </div>
            ) : (
                /* Audit Log List */
                <div style={{ background: "white", borderRadius: "16px", border: "1px solid #e5e5e5", overflow: "hidden" }}>
                    {logs.map(entry => (
                        <div key={entry.id} style={{
                            padding: "1rem 1.5rem",
                            borderBottom: "1px solid #f0f0f0",
                            display: "flex",
                            gap: "1rem",
                            alignItems: "flex-start"
                        }}>
                            <div style={{
                                width: "32px",
                                height: "32px",
                                background: "#f0f0f0",
                                borderRadius: "8px",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                color: "#666",
                                flexShrink: 0
                            }}>
                                {getActionIcon(entry.action)}
                            </div>
                            <div style={{ flex: 1 }}>
                                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.25rem" }}>
                                    <span style={{ fontWeight: 500 }}>{entry.action}</span>
                                    <span style={{ fontSize: "0.8125rem", color: "#999" }}>{formatTime(entry.created_at)}</span>
                                </div>
                                <div style={{ fontSize: "0.875rem", color: "#666", marginBottom: "0.25rem" }}>
                                    {entry.entity_type}: {entry.entity_id}
                                </div>
                                {entry.details && (
                                    <div style={{ fontSize: "0.8125rem", color: "#999" }}>{entry.details}</div>
                                )}
                                <div style={{
                                    fontSize: "0.75rem",
                                    color: "#999",
                                    marginTop: "0.375rem",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "0.375rem"
                                }}>
                                    <User size={12} />
                                    {entry.user_id || "system"}
                                </div>
                            </div>
                        </div>
                    ))}
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
