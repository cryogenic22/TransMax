"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { Button } from "@/components/ui/button"
import { GlassCard } from "@/components/ui/GlassCard"
import { StatusBadge } from "@/components/ui/StatusBadge"
import {
    FileText, Upload, Search, Clock, CheckCircle,
    AlertCircle, Loader2, ArrowRight, X, ShieldCheck
} from "lucide-react"

// Strict API Types
interface JobProfileRequest {
    archetype: string
    tier: string
    modality: string
}

interface JobResponse {
    job_id: string
    status: string
    created_at: string
    estimated_completion?: string
}

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001") + "/api/v1/translations"

export default function DashboardPage() {
    const router = useRouter()
    const [jobs, setJobs] = useState<JobResponse[]>([])
    const [searchQuery, setSearchQuery] = useState("")
    const [isLoading, setIsLoading] = useState(true)

    // Stats
    const stats = {
        total: jobs.length,
        pending: jobs.filter(j => ["processing", "uploaded"].includes(j.status)).length,
        review: jobs.filter(j => ["review_required", "in_review"].includes(j.status)).length,
        approved: jobs.filter(j => ["approved", "translated"].includes(j.status)).length
    }

    const fetchJobs = async () => {
        try {
            const res = await fetch(`${API_BASE}/?limit=50`)
            if (res.ok) {
                const data = await res.json()
                setJobs(data)
            }
        } catch (error) {
            console.error("Failed to fetch jobs", error)
        } finally {
            setIsLoading(false)
        }
    }

    useEffect(() => {
        fetchJobs()
        const interval = setInterval(fetchJobs, 5000)
        return () => clearInterval(interval)
    }, [])


    return (
        <main className="min-h-screen bg-slate-50 text-slate-900 font-sans">
            <header className="border-b bg-white sticky top-0 z-40 shadow-sm">
                <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center text-white font-bold">T</div>
                        <h1 className="text-xl font-bold tracking-tight text-slate-900">TransMax <span className="text-slate-400 font-normal">Control Tower</span></h1>
                    </div>
                    <div className="flex items-center gap-4">
                        <Button onClick={() => router.push("/workspace/tools")} variant="ghost" className="text-slate-600 hover:text-primary hover:bg-slate-100">
                            Knowledge Center
                        </Button>
                        <Button onClick={() => router.push("/workspace/upload")} className="bg-primary hover:bg-blue-800 text-white shadow-sm">
                            Initiate Protocol
                        </Button>
                    </div>
                </div>
            </header>

            <div className="max-w-7xl mx-auto px-6 py-8">
                {/* Stats */}
                <div className="grid grid-cols-4 gap-4 mb-8">
                    <GlassCard>
                        <div className="text-xs font-medium text-slate-500 uppercase tracking-widest mb-1">Total Jobs</div>
                        <div className="text-3xl font-bold text-slate-800">{stats.total}</div>
                    </GlassCard>
                    <GlassCard className="border-l-4 border-l-blue-500">
                        <div className="text-xs font-medium text-slate-500 uppercase tracking-widest mb-1">Processing</div>
                        <div className="text-3xl font-bold text-blue-600">{stats.pending}</div>
                    </GlassCard>
                    <GlassCard className="border-l-4 border-l-amber-400">
                        <div className="text-xs font-medium text-slate-500 uppercase tracking-widest mb-1">Needs Review</div>
                        <div className="text-3xl font-bold text-amber-600">{stats.review}</div>
                    </GlassCard>
                    <GlassCard className="border-l-4 border-l-medical-green">
                        <div className="text-xs font-medium text-slate-500 uppercase tracking-widest mb-1">Approved</div>
                        <div className="text-3xl font-bold text-green-700">{stats.approved}</div>
                    </GlassCard>
                </div>

                {/* List */}
                <GlassCard className="p-0 overflow-hidden">
                    <div className="p-4 border-b bg-slate-50/50 flex items-center justify-between">
                        <h3 className="font-semibold text-slate-700">Recent Translations</h3>
                        <Button variant="ghost" size="sm" onClick={fetchJobs}><Clock className="w-3 h-3 mr-1" /> Refresh</Button>
                    </div>

                    <div className="max-h-[600px] overflow-y-auto">
                        <table className="w-full text-sm text-left">
                            <thead className="text-xs text-slate-500 uppercase bg-slate-50 sticky top-0">
                                <tr>
                                    <th className="px-6 py-3 font-medium">Job ID</th>
                                    <th className="px-6 py-3 font-medium">Status</th>
                                    <th className="px-6 py-3 font-medium">Submitted</th>
                                    <th className="px-6 py-3 font-medium"></th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {jobs.map((job) => (
                                    <tr
                                        key={job.job_id}
                                        onClick={() => router.push(`/review/${job.job_id}`)}
                                        className="hover:bg-slate-50 cursor-pointer transition-colors"
                                    >
                                        <td className="px-6 py-4 font-mono text-slate-600">{job.job_id.substring(0, 8)}...</td>
                                        <td className="px-6 py-4">
                                            <StatusBadge status={job.status.toUpperCase()} />
                                        </td>
                                        <td className="px-6 py-4 text-slate-500">
                                            {new Date(job.created_at).toLocaleString()}
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            {["approved", "translated"].includes(job.status.toLowerCase()) && (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    className="mr-2 text-xs"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        window.open(`${API_BASE}/${job.job_id}/certificate`, '_blank');
                                                    }}
                                                >
                                                    <ShieldCheck className="w-3 h-3 mr-1 text-green-600" /> Cert
                                                </Button>
                                            )}
                                            <ArrowRight className="w-4 h-4 text-slate-300 inline" />
                                        </td>
                                    </tr>
                                ))}
                                {jobs.length === 0 && !isLoading && (
                                    <tr>
                                        <td colSpan={4} className="px-6 py-12 text-center text-slate-400">
                                            No active jobs. Submit a new translation.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </GlassCard>
            </div>
        </main>
    )
}
