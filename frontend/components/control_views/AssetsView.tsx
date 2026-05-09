"use client"
import React, { useState, useEffect } from "react"
import { BookOpen, ArrowRight } from "lucide-react"
import { useRouter } from "next/navigation"
import { api } from "@/lib/api"

export function AssetsView() {
    const router = useRouter()
    const [ruleCount, setRuleCount] = useState<number | null>(null)
    const [pendingCount, setPendingCount] = useState<number | null>(null)
    const [glossaryCount, setGlossaryCount] = useState<number | null>(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        const fetchCounts = async () => {
            try {
                const [allRules, pendingRules, glossaries] = await Promise.all([
                    api.knowledge.listRules().catch(() => []),
                    api.knowledge.listRules("PENDING_APPROVAL").catch(() => []),
                    api.knowledge.listGlossaries().catch(() => []),
                ])
                setRuleCount(allRules.length)
                setPendingCount(pendingRules.length)
                setGlossaryCount(glossaries.length)
            } catch (e) {
                console.error("Failed to fetch asset counts:", e)
            } finally {
                setLoading(false)
            }
        }
        fetchCounts()
    }, [])

    return (
        <div className="space-y-6">
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <SummaryCard
                    title="Translation Rules"
                    value={loading ? "..." : String(ruleCount ?? 0)}
                    subtitle="Active in Black Book"
                    color="blue"
                />
                <SummaryCard
                    title="Pending Review"
                    value={loading ? "..." : String(pendingCount ?? 0)}
                    subtitle="Awaiting approval"
                    color="amber"
                />
                <SummaryCard
                    title="Glossaries"
                    value={loading ? "..." : String(glossaryCount ?? 0)}
                    subtitle="Loaded glossary packs"
                    color="indigo"
                />
            </div>

            {/* Action Buttons */}
            <div className="flex flex-wrap gap-3">
                <button
                    onClick={() => router.push("/workspace/tools")}
                    className="flex items-center gap-2 px-5 py-3 bg-blue-600 text-white font-medium rounded-xl hover:bg-blue-700 transition-colors shadow-sm"
                >
                    <BookOpen size={18} /> Manage Rules
                    <ArrowRight size={16} className="ml-1" />
                </button>
                <button
                    onClick={() => router.push("/workspace/tools?tab=glossaries")}
                    className="flex items-center gap-2 px-5 py-3 bg-white text-slate-700 font-medium rounded-xl border border-slate-200 hover:bg-slate-50 transition-colors shadow-sm"
                >
                    <BookOpen size={18} /> View Glossaries
                    <ArrowRight size={16} className="ml-1" />
                </button>
                <button
                    onClick={() => router.push("/workspace/tools?tab=import-export")}
                    className="flex items-center gap-2 px-5 py-3 bg-white text-slate-700 font-medium rounded-xl border border-slate-200 hover:bg-slate-50 transition-colors shadow-sm"
                >
                    Import / Export
                    <ArrowRight size={16} className="ml-1" />
                </button>
            </div>
        </div>
    )
}

function SummaryCard({ title, value, subtitle, color }: { title: string; value: string; subtitle: string; color: string }) {
    const bgMap: Record<string, string> = { blue: "bg-blue-50", amber: "bg-amber-50", indigo: "bg-indigo-50" }
    const textMap: Record<string, string> = { blue: "text-blue-700", amber: "text-amber-700", indigo: "text-indigo-700" }
    const iconMap: Record<string, string> = { blue: "text-blue-600", amber: "text-amber-600", indigo: "text-indigo-600" }

    return (
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
            <div className="flex items-center gap-3 mb-3">
                <div className={`p-2.5 rounded-lg ${bgMap[color]}`}>
                    <BookOpen size={20} className={iconMap[color]} />
                </div>
                <span className="text-sm font-medium text-slate-500">{title}</span>
            </div>
            <div className={`text-3xl font-bold ${textMap[color]} mb-1`}>{value}</div>
            <div className="text-xs text-slate-400">{subtitle}</div>
        </div>
    )
}
