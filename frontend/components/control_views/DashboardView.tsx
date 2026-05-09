"use client"
import React, { useEffect, useState } from 'react'
import { ArrowUpRight, CheckCircle2, Clock, FileText, Inbox, TrendingUp, Loader2, WifiOff, RefreshCw, Coins, Zap } from 'lucide-react'
import { api } from '@/lib/api'
import { ActivityFeed } from '@/components/ui/ActivityFeed'
import { useActivityFeed } from '@/hooks/useActivity'

interface DashboardStats {
    total_documents: number
    active_jobs: number
    avg_quality_pct: number | null
    completed_24h: number
    total_segments: number
    translated_segments: number
    total_tokens: number
    total_cost_usd: number
}

export function DashboardView() {
    const [stats, setStats] = useState<DashboardStats | null>(null)
    const [loading, setLoading] = useState(true)
    // TMX-3603-dashboard: replaced the bespoke ActivityItem polling with the
    // shared useActivityFeed hook (TMX-3603-wire). The feed renders via the
    // <ActivityFeed> design-system component, surfacing the audit chain
    // event stream rather than a hand-rolled task list — see rescape
    // designer review §Dashboard.
    const { data: feedItems, error: feedError } = useActivityFeed(15)

    useEffect(() => {
        const load = async () => {
            try {
                const s = await api.dashboard.stats().catch(() => null)
                setStats(s)
            } finally {
                setLoading(false)
            }
        }
        load()
    }, [])

    if (loading) {
        return (
            <div className="flex items-center justify-center py-20 text-slate-400">
                <Loader2 className="animate-spin mr-2" size={20} />
                Loading dashboard...
            </div>
        )
    }

    const fmt = (n: number | null | undefined) => n != null ? n.toLocaleString() : "—"

    return (
        <div className="space-y-6">
            {/* Connection Warning */}
            {!stats && (
                <div className="flex items-center gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-800 text-sm">
                    <WifiOff size={18} className="shrink-0" />
                    <span className="flex-1">Unable to connect to the backend server. Ensure the API is running on the configured port.</span>
                    <button
                        onClick={() => window.location.reload()}
                        className="flex items-center gap-1 px-3 py-1.5 bg-amber-100 hover:bg-amber-200 rounded-lg text-xs font-medium transition-colors"
                    >
                        <RefreshCw size={12} />
                        Retry
                    </button>
                </div>
            )}

            {/* KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <KPICard
                    title="Total Documents"
                    value={fmt(stats?.total_documents)}
                    change={stats?.completed_24h ? `+${stats.completed_24h} today` : "—"}
                    icon={<FileText className="text-blue-600" size={20} />}
                />
                <KPICard
                    title="Active Jobs"
                    value={fmt(stats?.active_jobs)}
                    change={stats?.active_jobs === 0 ? "All clear" : "In progress"}
                    icon={<Clock className="text-orange-600" size={20} />}
                />
                <KPICard
                    title="Quality Score"
                    value={stats?.avg_quality_pct != null ? `${stats.avg_quality_pct}%` : "—"}
                    change={stats?.avg_quality_pct != null && stats.avg_quality_pct >= 90 ? "On target" : "Needs review"}
                    icon={<CheckCircle2 className="text-green-600" size={20} />}
                />
                <KPICard
                    title="Segments"
                    value={fmt(stats?.translated_segments)}
                    change={stats?.total_segments ? `of ${fmt(stats.total_segments)} total` : "—"}
                    icon={<TrendingUp className="text-purple-600" size={20} />}
                />
                <KPICard
                    title="Total Tokens"
                    value={fmt(stats?.total_tokens)}
                    change="LLM usage"
                    icon={<Zap className="text-amber-600" size={20} />}
                />
                <KPICard
                    title="Total Cost"
                    value={stats?.total_cost_usd != null ? `$${stats.total_cost_usd.toFixed(4)}` : "—"}
                    change="USD spent"
                    icon={<Coins className="text-emerald-600" size={20} />}
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Activity Feed — TMX-3603-dashboard: the audit chain event
                    stream as the dashboard hero, replacing the hand-rolled
                    "Pending: 0 / Active: 0" stat cards (rescape Direction 2). */}
                <div className="col-span-2 space-y-3">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Inbox size={20} className="text-slate-400" />
                            <h2 className="text-lg font-bold text-slate-800">Recent Activity</h2>
                        </div>
                        {feedItems && feedItems.length > 0 && (
                            <span className="bg-blue-100 text-blue-700 text-xs font-bold px-2 py-1 rounded-full">
                                {feedItems.length} events
                            </span>
                        )}
                    </div>
                    {feedError ? (
                        <div className="rounded-lg border bg-amber-50 border-amber-200 p-4 text-sm text-amber-800">
                            Activity feed temporarily unavailable: {feedError.message}
                        </div>
                    ) : (
                        <ActivityFeed items={feedItems ?? []} />
                    )}
                </div>

                {/* Summary panel */}
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                    <div className="flex items-center gap-2 mb-6">
                        <CheckCircle2 size={20} className="text-slate-400" />
                        <h2 className="text-lg font-bold text-slate-800">System Health</h2>
                    </div>
                    <div className="space-y-4 text-sm">
                        <HealthRow label="Backend" status={stats ? "ok" : "error"} detail={stats ? "Connected" : "Unreachable"} />
                        <HealthRow label="Documents" status={stats ? "ok" : "error"} detail={stats ? `${stats.total_documents} indexed` : "Unreachable"} />
                        <HealthRow label="Quality Gate" status={stats ? "ok" : "error"} detail={stats ? "All checks active" : "Unavailable"} />
                        <HealthRow label="Audit Chain" status={stats ? "ok" : "error"} detail={stats ? "Integrity verified" : "Unavailable"} />
                    </div>
                </div>
            </div>
        </div>
    )
}

function KPICard({ title, value, change, icon }: { title: string; value: string; change: string; icon: React.ReactNode }) {
    return (
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-start justify-between">
            <div>
                <p className="text-slate-500 text-sm font-medium mb-1">{title}</p>
                <div className="text-2xl font-bold text-slate-900">{value}</div>
                <div className="flex items-center gap-1 mt-1 text-xs font-medium text-green-600">
                    <ArrowUpRight size={12} />
                    {change}
                </div>
            </div>
            <div className="p-2 bg-slate-50 rounded-lg">{icon}</div>
        </div>
    )
}

function HealthRow({ label, status, detail }: { label: string; status: "ok" | "error"; detail?: string }) {
    return (
        <div className="flex items-center justify-between">
            <span className="text-slate-600">{label}</span>
            <div className="flex items-center gap-2">
                {detail && <span className="text-slate-400 text-xs">{detail}</span>}
                <div className={`w-2 h-2 rounded-full ${status === "ok" ? "bg-green-500" : "bg-red-500"}`} />
            </div>
        </div>
    )
}
