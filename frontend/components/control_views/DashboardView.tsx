"use client"
import React, { useEffect, useState } from 'react'
import { CheckCircle2, Inbox, Loader2, WifiOff, RefreshCw } from 'lucide-react'
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

            {/* TMX-3603-statstrip: rescape Direction 2 — Activity Feed as
                the dashboard HERO, system health beside it, KPI cards
                demoted to a small footer strip. The 6 stat cards used to
                dominate the page even when most were 0; now they fit on
                one horizontal line and the eye lands on the audit stream. */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Activity Feed (hero) */}
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

                {/* System Health (sidebar) */}
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

            {/* Stat Strip — compressed footer summary (rescape: "demote
                stat-cards"). Six numbers in one row, scannable, no
                individual card chrome. */}
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 divide-y sm:divide-y-0 sm:divide-x divide-slate-100">
                    <StatStripItem label="Documents" value={fmt(stats?.total_documents)} sub={stats?.completed_24h ? `+${stats.completed_24h} 24h` : null} />
                    <StatStripItem label="Active" value={fmt(stats?.active_jobs)} sub={stats?.active_jobs === 0 ? "all clear" : "in flight"} />
                    <StatStripItem label="Quality" value={stats?.avg_quality_pct != null ? `${stats.avg_quality_pct}%` : "—"} sub={stats?.avg_quality_pct != null && stats.avg_quality_pct >= 90 ? "on target" : "needs review"} />
                    <StatStripItem label="Segments" value={fmt(stats?.translated_segments)} sub={stats?.total_segments ? `of ${fmt(stats.total_segments)}` : null} />
                    <StatStripItem label="Tokens" value={fmt(stats?.total_tokens)} sub="LLM usage" />
                    <StatStripItem label="Cost" value={stats?.total_cost_usd != null ? `$${stats.total_cost_usd.toFixed(4)}` : "—"} sub="USD" />
                </div>
            </div>
        </div>
    )
}

function StatStripItem({ label, value, sub }: { label: string; value: string; sub?: string | null }) {
    return (
        <div className="px-3 py-2">
            <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</div>
            <div className="text-lg font-semibold text-slate-900 leading-tight">{value}</div>
            {sub ? <div className="text-[11px] text-slate-400 mt-0.5">{sub}</div> : null}
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
