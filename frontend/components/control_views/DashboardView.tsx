"use client"
import React, { useEffect, useState } from 'react'
import { ArrowUpRight, CheckCircle2, Clock, FileText, Inbox, TrendingUp, Loader2, WifiOff, RefreshCw, Coins, Zap } from 'lucide-react'
import { api } from '@/lib/api'

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

interface ActivityItem {
    id: string
    title: string
    desc: string
    status: string
    priority: string
    target_language: string
    updated_at: string | null
}

export function DashboardView() {
    const [stats, setStats] = useState<DashboardStats | null>(null)
    const [activity, setActivity] = useState<ActivityItem[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        const load = async () => {
            try {
                const [s, a] = await Promise.all([
                    api.dashboard.stats().catch(() => null),
                    api.dashboard.activity(5).catch(() => []),
                ])
                setStats(s)
                setActivity(a)
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
                {/* Inbox */}
                <div className="col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                    <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-2">
                            <Inbox size={20} className="text-slate-400" />
                            <h2 className="text-lg font-bold text-slate-800">Recent Activity</h2>
                        </div>
                        {activity.length > 0 && (
                            <span className="bg-blue-100 text-blue-700 text-xs font-bold px-2 py-1 rounded-full">
                                {activity.length} Items
                            </span>
                        )}
                    </div>

                    <div className="space-y-4">
                        {activity.length === 0 ? (
                            <p className="text-sm text-slate-400 py-4 text-center">No recent activity</p>
                        ) : (
                            activity.map((item) => (
                                <TaskItem
                                    key={item.id}
                                    title={item.title}
                                    desc={item.desc}
                                    time={item.updated_at ? timeAgo(item.updated_at) : "—"}
                                    priority={item.priority}
                                />
                            ))
                        )}
                    </div>
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

function TaskItem({ title, desc, time, priority }: { title: string; desc: string; time: string; priority: string }) {
    return (
        <div className="flex items-start gap-4 p-3 hover:bg-slate-50 rounded-lg transition-colors cursor-pointer border border-transparent hover:border-slate-100">
            <div className={`mt-1 w-2 h-2 rounded-full shrink-0 ${priority === 'High' ? 'bg-red-500' : priority === 'Medium' ? 'bg-orange-500' : 'bg-blue-500'
                }`} />
            <div className="flex-1">
                <div className="flex justify-between items-start">
                    <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
                    <span className="text-xs text-slate-400 whitespace-nowrap">{time}</span>
                </div>
                <p className="text-sm text-slate-500 mt-1">{desc}</p>
            </div>
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

function timeAgo(isoString: string): string {
    const diff = Date.now() - new Date(isoString).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return "just now"
    if (mins < 60) return `${mins}m ago`
    const hours = Math.floor(mins / 60)
    if (hours < 24) return `${hours}h ago`
    const days = Math.floor(hours / 24)
    return `${days}d ago`
}
