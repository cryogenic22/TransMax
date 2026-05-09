"use client"
import React, { useState, useEffect } from "react"
import { Shield, Lock, CheckCircle, History, User, FileText, Activity, Edit3, RefreshCw } from "lucide-react"
import { api, AuditLog } from "@/lib/api"

export function ComplianceView() {
    return (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
            {/* Left Column: Privacy Monitor */}
            <div className="xl:col-span-1 space-y-6">
                <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                    <Shield className="text-green-600" size={24} />
                    Privacy Monitor
                </h2>
                <PrivacyCards />
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

function PrivacyCards() {
    return (
        <div className="space-y-4">
            <div className="bg-white p-5 rounded-xl border-l-4 border-l-green-500 border-y border-r border-slate-200 shadow-sm">
                <h3 className="font-semibold flex items-center gap-2 mb-2 text-slate-800">
                    <Lock className="text-green-600" size={18} />
                    Zero Retention (Azure OpenAI)
                </h3>
                <p className="text-sm text-slate-600 mb-4 leading-relaxed">
                    Data passed to the LLM is <strong>not stored</strong> or used for training models.
                    Enforced via API policy `opt-out: true`.
                </p>
                <div className="flex items-center gap-2 text-xs font-mono bg-green-50 text-green-800 p-2 rounded border border-green-100">
                    <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
                    Policy Active: NO_STORE
                </div>
            </div>

            <div className="bg-white p-5 rounded-xl border-l-4 border-l-blue-500 border-y border-r border-slate-200 shadow-sm">
                <h3 className="font-semibold flex items-center gap-2 mb-2 text-slate-800">
                    <Shield className="text-blue-600" size={18} />
                    PII Redaction Shield
                </h3>
                <p className="text-sm text-slate-600 mb-4 leading-relaxed">
                    Personally Identifiable Information (Names, Dates, MRNs) is masked
                    <strong> before</strong> leaving the secure perimeter.
                </p>
                <div className="flex items-center gap-2 text-xs font-mono bg-blue-50 text-blue-800 p-2 rounded border border-blue-100">
                    <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></div>
                    Scrubber Active: NER_V2_EN
                </div>
            </div>

            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <h3 className="font-semibold mb-3 text-slate-800 text-sm uppercase tracking-wide">Privacy Impact Assessment</h3>
                <div className="space-y-3">
                    <div className="flex justify-between items-center p-2 bg-slate-50 rounded border border-slate-100">
                        <span className="text-sm font-medium text-slate-700">Data Residency</span>
                        <span className="text-xs font-bold text-slate-600 bg-white px-2 py-1 rounded border border-slate-200">US-EAST-2</span>
                    </div>
                    <div className="flex justify-between items-center p-2 bg-slate-50 rounded border border-slate-100">
                        <span className="text-sm font-medium text-slate-700">Encryption</span>
                        <span className="text-xs font-bold text-green-700 flex items-center gap-1 bg-green-50 px-2 py-1 rounded border border-green-200">
                            <CheckCircle size={10} /> AES-256
                        </span>
                    </div>
                    <div className="flex justify-between items-center p-2 bg-slate-50 rounded border border-slate-100">
                        <span className="text-sm font-medium text-slate-700">Immutability</span>
                        <span className="text-xs font-bold text-green-700 flex items-center gap-1 bg-green-50 px-2 py-1 rounded border border-green-200">
                            <CheckCircle size={10} /> SHA-256
                        </span>
                    </div>
                </div>
            </div>
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
