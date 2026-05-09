"use client"
import React, { useState, useEffect } from "react"
import { BookOpen, ArrowRight } from "lucide-react"
import { useRouter } from "next/navigation"
import { api } from "@/lib/api"
import { getErrMessage } from "@/lib/utils"

export function AssetsView() {
    const router = useRouter()
    const [ruleCount, setRuleCount] = useState<number | null>(null)
    const [pendingCount, setPendingCount] = useState<number | null>(null)
    const [glossaryCount, setGlossaryCount] = useState<number | null>(null)
    const [loading, setLoading] = useState(true)
    // TMX-3604-assets-err: A3 — empty-vs-failure must be visually distinct
    // for a regulator auditing rule coverage. `null` count = "didn't load",
    // `0` = "loaded, no rows yet". Pre-fix .catch(() => []) collapsed
    // both into "0", indistinguishable to the reviewer.
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        const fetchCounts = async () => {
            const [r, p, g] = await Promise.allSettled([
                api.knowledge.listRules(),
                api.knowledge.listRules("PENDING_APPROVAL"),
                api.knowledge.listGlossaries(),
            ])
            if (r.status === "fulfilled") setRuleCount(r.value.length)
            if (p.status === "fulfilled") setPendingCount(p.value.length)
            if (g.status === "fulfilled") setGlossaryCount(g.value.length)
            const firstErr = [r, p, g].find(x => x.status === "rejected") as
                | PromiseRejectedResult
                | undefined
            if (firstErr) {
                setError(getErrMessage(firstErr.reason, "Failed to load assets"))
            }
            setLoading(false)
        }
        fetchCounts()
    }, [])

    // Pivot card display so a failed fetch shows "—" not "0".
    const display = (n: number | null) =>
        loading ? "..." : n == null ? "—" : String(n)

    return (
        <div className="space-y-6">
            {/* TMX-3604-assets-err: real server error visible above the
                cards so a 0/0/0 failure state is never mistaken for a
                legitimate empty Black Book. */}
            {error ? (
                <div
                    role="status"
                    aria-label="Assets failed to load"
                    className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
                >
                    <strong>Couldn&apos;t load assets.</strong> {error}
                </div>
            ) : null}

            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <SummaryCard
                    title="Translation Rules"
                    value={display(ruleCount)}
                    subtitle="Active in Black Book"
                    color="blue"
                />
                <SummaryCard
                    title="Pending Review"
                    value={display(pendingCount)}
                    subtitle="Awaiting approval"
                    color="amber"
                />
                <SummaryCard
                    title="Glossaries"
                    value={display(glossaryCount)}
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
