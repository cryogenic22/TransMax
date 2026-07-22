"use client"
import React, { useState, useEffect } from "react"
import Link from "next/link"
import { Shield, Lock, CheckCircle, XCircle, History, User, FileText, Activity, Edit3, RefreshCw, ExternalLink } from "lucide-react"
import { api, AuditLog, TrustPosture } from "@/lib/api"

export function ComplianceView() {
    return (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
            {/* Left Column: Privacy Monitor */}
            <div className="xl:col-span-1 space-y-6">
                <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                    <Shield className="text-green-600" size={24} />
                    Privacy Monitor
                </h2>
                <PrivacyPosture />
            </div>

            {/* Right Column: Audit Log */}
            <div className="xl:col-span-2 space-y-6">
                <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                    <History className="text-blue-600" size={24} />
                    Audit Trail
                </h2>
                <AuditLogList />
            </div>
        </div>
    )
}

// TMX-POSTURE-FAB (A3): real posture only — the previous static cards here
// fabricated retention/scrubber/encryption claims the product does not have.
// Everything below is fetched from the backend's trust-posture endpoint;
// on failure we fail loud, never substitute.
function PrivacyPosture() {
    const [posture, setPosture] = useState<TrustPosture | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const fetchPosture = async () => {
        setLoading(true)
        setError(null)
        try {
            setPosture(await api.trust.getPosture())
        } catch (e) {
            setError(e instanceof Error ? e.message : "Failed to load trust posture")
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => { fetchPosture() }, [])

    if (loading) {
        return <div className="p-8 text-center text-slate-500 bg-white rounded-xl border border-slate-200">Loading trust posture...</div>
    }

    if (error) {
        return (
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm text-center">
                <XCircle className="text-red-500 mx-auto mb-2" size={24} />
                <h3 className="text-red-600 font-medium text-sm">Couldn&apos;t load trust posture</h3>
                <p className="text-slate-500 text-xs mt-1">{error}</p>
                <button onClick={fetchPosture} className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-blue-600 hover:text-blue-700">
                    <RefreshCw size={12} /> Retry
                </button>
            </div>
        )
    }

    const controls = posture?.controls ?? []

    return (
        <div className="space-y-4">
            <p className="text-xs text-slate-500 leading-relaxed">
                Self-reported controls. Items marked <span className="font-medium text-amber-600">Not verified in-app</span> are
                infrastructure- or policy-level and must be confirmed in the deployment environment.
            </p>
            {controls.length === 0 ? (
                <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm text-center">
                    <h3 className="text-slate-900 font-medium text-sm">No posture controls reported</h3>
                    <p className="text-slate-500 text-xs mt-1">The trust posture endpoint returned no controls.</p>
                </div>
            ) : (
                controls.map((c) => (
                    <div
                        key={c.key}
                        className={`bg-white p-5 rounded-xl border-l-4 ${c.verified ? "border-l-green-500" : "border-l-amber-400"} border-y border-r border-slate-200 shadow-sm`}
                    >
                        <div className="flex items-start justify-between gap-3">
                            <div>
                                <h3 className="font-semibold flex items-center gap-2 text-slate-800">
                                    {c.verified
                                        ? <Lock className="text-green-600" size={18} />
                                        : <Shield className="text-amber-500" size={18} />}
                                    {c.label}
                                </h3>
                                <p className="text-sm text-slate-700 mt-1 font-mono">{c.value}</p>
                                <p className="text-xs text-slate-500 mt-2 leading-relaxed">{c.detail}</p>
                            </div>
                            <span
                                className={`shrink-0 px-2 py-1 rounded-full text-xs font-medium flex items-center gap-1 ${c.verified ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}
                            >
                                {c.verified ? <CheckCircle size={12} /> : <XCircle size={12} />}
                                {c.verified ? "Verified" : "Not verified in-app"}
                            </span>
                        </div>
                    </div>
                ))
            )}
            <Link href="/workspace/trust" className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-600 hover:text-blue-700">
                <ExternalLink size={12} /> Full trust posture in the Trust Center
            </Link>
        </div>
    )
}

function AuditLogList() {
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

    useEffect(() => { fetchLogs() }, [])

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
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
        return date.toLocaleDateString()
    }

    if (loading) return <div className="p-8 text-center text-slate-500 bg-white rounded-xl border border-slate-200">Loading audit trail...</div>

    return (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col h-[600px]">
            <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                <span className="text-xs font-bold text-slate-500 uppercase">Recent Activity Stream</span>
                <button onClick={fetchLogs} className="text-slate-400 hover:text-blue-600 transition-colors">
                    <RefreshCw size={14} />
                </button>
            </div>

            <div className="overflow-y-auto flex-1 p-0">
                {logs.length === 0 ? (
                    <div className="p-12 text-center">
                        <h3 className="text-slate-900 font-medium">No activity recorded</h3>
                        <p className="text-slate-500 text-sm mt-1">Actions perform will appear here.</p>
                    </div>
                ) : (
                    <div className="divide-y divide-slate-50">
                        {logs.map(entry => (
                            <div key={entry.id} className="p-4 flex gap-4 hover:bg-slate-50/80 transition-colors group">
                                <div className="relative">
                                    <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-500 group-hover:bg-white group-hover:shadow-sm group-hover:text-blue-600 transition-all border border-slate-200 group-hover:border-blue-100">
                                        {getActionIcon(entry.action)}
                                    </div>
                                    <div className="absolute top-8 left-1/2 w-px h-full bg-slate-100 -translate-x-1/2 -z-10 group-last:hidden"></div>
                                </div>

                                <div className="flex-1">
                                    <div className="flex justify-between items-start">
                                        <span className="font-semibold text-sm text-slate-800">{entry.action}</span>
                                        <span className="text-xs text-slate-400 whitespace-nowrap">{formatTime(entry.created_at)}</span>
                                    </div>
                                    <div className="text-xs text-slate-500 mt-0.5">
                                        <span className="font-mono text-slate-400 bg-slate-50 px-1 rounded">{entry.entity_type}</span> <span className="text-slate-300">•</span> {entry.details || entry.entity_id}
                                    </div>
                                    <div className="mt-2 flex items-center gap-1.5 text-xs text-slate-400">
                                        <User size={10} />
                                        <span>{entry.user_id || "System"}</span>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    )
}
