"use client"

import { useState, useEffect, useCallback, useRef, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import {
    ArrowLeft, Book, Check, X, Search, Plus, Trash2, Edit3, Play,
    Download, Upload, BarChart3, BookOpen, FileText,
    AlertTriangle, RefreshCw
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { GlassCard } from "@/components/ui/GlassCard"
import { LanguageSelector } from "@/components/ui/LanguageSelector"
import { api } from "@/lib/api"
import { getErrMessage } from "@/lib/utils"

// ─── Types ───────────────────────────────────────────────────────────────────

interface Rule {
    rule_id: string
    source_pattern: string
    target_correction: string
    context_tag: string
    confidence_score: number
    status: string
    source_language?: string
    target_language?: string
    domain?: string
    is_regex: boolean
    is_strict: boolean
    priority: number
    description?: string
    fire_count: number
    false_positive_count: number
    created_by?: string
    created_at: string
}

interface Glossary {
    glossary_id: string
    version: string
    is_active: boolean
    meta_json?: { source_language?: string; target_language?: string } | null
    term_count?: number
    created_at: string
}

interface GlossaryTerm {
    term_id: string
    source_text: string
    target_text: string
    is_forbidden: boolean
    allowed_variants: string[]
}

interface AnalyticsEntry {
    rule_id: string
    source_pattern: string
    fire_count: number
    false_positive_count: number
    effectiveness: number
}

type TabKey = "rules" | "glossaries" | "import-export"
type StatusFilter = "ALL" | "ACTIVE" | "PENDING_APPROVAL" | "REJECTED"

const STATUS_FILTERS: { key: StatusFilter; label: string; color: string }[] = [
    { key: "ALL", label: "All", color: "bg-slate-100 text-slate-700" },
    { key: "ACTIVE", label: "Active", color: "bg-green-100 text-green-700" },
    { key: "PENDING_APPROVAL", label: "Pending", color: "bg-amber-100 text-amber-700" },
    { key: "REJECTED", label: "Rejected", color: "bg-red-100 text-red-700" },
]

const DOMAINS = ["general", "pharma", "legal", "medical", "financial", "technical"]

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function KnowledgePage() {
    return (
        <Suspense fallback={<div className="min-h-screen bg-slate-50 flex items-center justify-center text-slate-400">Loading...</div>}>
            <KnowledgePageInner />
        </Suspense>
    )
}

function KnowledgePageInner() {
    const router = useRouter()
    const searchParams = useSearchParams()
    const initialTab = (searchParams.get("tab") as TabKey) || "rules"
    const [activeTab, setActiveTab] = useState<TabKey>(initialTab)

    return (
        <main className="min-h-screen bg-slate-50 font-sans pb-20">
            <header className="bg-white border-b border-slate-200 sticky top-0 z-40 shadow-sm">
                <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <Button variant="ghost" size="icon" onClick={() => router.push("/workspace")}>
                            <ArrowLeft className="w-5 h-5 text-slate-500" />
                        </Button>
                        <div>
                            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
                                <Book className="w-5 h-5 text-primary" /> Black Book
                            </h1>
                            <p className="text-xs text-slate-500 font-mono">Knowledge Base &bull; Rules &bull; Glossaries</p>
                        </div>
                    </div>
                </div>
            </header>

            <div className="max-w-7xl mx-auto px-6 py-6">
                {/* Tab Navigation */}
                <div className="flex bg-white p-1 rounded-lg border border-slate-200 w-fit mb-6">
                    {([
                        { key: "rules" as TabKey, label: "Rules", icon: Book },
                        { key: "glossaries" as TabKey, label: "Glossaries", icon: BookOpen },
                        { key: "import-export" as TabKey, label: "Import / Export", icon: FileText },
                    ]).map(tab => (
                        <button
                            key={tab.key}
                            onClick={() => setActiveTab(tab.key)}
                            className={`px-4 py-2 text-sm font-medium rounded-md transition-all flex items-center gap-2 ${activeTab === tab.key
                                ? 'bg-slate-800 text-white shadow-sm'
                                : 'text-slate-500 hover:bg-slate-50'
                                }`}
                        >
                            <tab.icon className="w-4 h-4" /> {tab.label}
                        </button>
                    ))}
                </div>

                <AnimatePresence mode="wait">
                    <motion.div
                        key={activeTab}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        transition={{ duration: 0.15 }}
                    >
                        {activeTab === "rules" && <RulesTab />}
                        {activeTab === "glossaries" && <GlossariesTab />}
                        {activeTab === "import-export" && <ImportExportTab />}
                    </motion.div>
                </AnimatePresence>
            </div>
        </main>
    )
}

// ─── Tab 1: Rules ────────────────────────────────────────────────────────────

function RulesTab() {
    const [rules, setRules] = useState<Rule[]>([])
    const [loading, setLoading] = useState(true)
    const [connectionError, setConnectionError] = useState<string | null>(null)
    const [searchQuery, setSearchQuery] = useState("")
    const [statusFilter, setStatusFilter] = useState<StatusFilter>("ALL")
    const [domainFilter, setDomainFilter] = useState("")
    const [showCreateModal, setShowCreateModal] = useState(false)
    const [editingRule, setEditingRule] = useState<Rule | null>(null)
    const [deletingId, setDeletingId] = useState<string | null>(null)

    const fetchRules = useCallback(async () => {
        setLoading(true)
        setConnectionError(null)
        try {
            const status = statusFilter === "ALL" ? undefined : statusFilter
            const data = await api.knowledge.listRules(status)
            setRules(data)
        } catch (e) {
            console.error("Failed to load rules:", e)
            setConnectionError(getErrMessage(e, "Failed to load rules"))
        } finally {
            setLoading(false)
        }
    }, [statusFilter])

    useEffect(() => { fetchRules() }, [fetchRules])

    const handleApprove = async (ruleId: string) => {
        try {
            await api.knowledge.updateRule(ruleId, "ACTIVE")
            fetchRules()
        } catch (e) { console.error("Approve failed:", e) }
    }

    const handleReject = async (ruleId: string) => {
        try {
            await api.knowledge.updateRule(ruleId, "REJECTED")
            fetchRules()
        } catch (e) { console.error("Reject failed:", e) }
    }

    const handleDelete = async (ruleId: string) => {
        try {
            await api.knowledge.deleteRule(ruleId)
            setDeletingId(null)
            fetchRules()
        } catch (e) { console.error("Delete failed:", e) }
    }

    const filteredRules = rules.filter(r => {
        const q = searchQuery.toLowerCase()
        if (q && !r.source_pattern.toLowerCase().includes(q) && !r.target_correction.toLowerCase().includes(q)) return false
        if (domainFilter && r.domain !== domainFilter) return false
        return true
    })

    return (
        <div>
            {/* Connection Error Banner */}
            {connectionError && (
                <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-xl flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0" />
                        <span className="text-sm text-red-700">{connectionError}</span>
                    </div>
                    <button onClick={fetchRules} className="text-sm font-medium text-red-600 hover:text-red-800 flex items-center gap-1">
                        <RefreshCw className="w-3.5 h-3.5" /> Retry
                    </button>
                </div>
            )}
            {/* Toolbar */}
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-4">
                <div className="flex flex-wrap items-center gap-2">
                    {STATUS_FILTERS.map(sf => (
                        <button
                            key={sf.key}
                            onClick={() => setStatusFilter(sf.key)}
                            className={`px-3 py-1.5 text-xs font-semibold rounded-full transition-all ${statusFilter === sf.key ? sf.color + " ring-2 ring-offset-1 ring-slate-300" : "bg-slate-50 text-slate-400 hover:bg-slate-100"}`}
                        >
                            {sf.label}
                        </button>
                    ))}
                    <select
                        value={domainFilter}
                        onChange={e => setDomainFilter(e.target.value)}
                        className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white text-slate-600"
                    >
                        <option value="">All Domains</option>
                        {DOMAINS.map(d => <option key={d} value={d}>{d}</option>)}
                    </select>
                </div>
                <div className="flex items-center gap-3">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                        <input
                            type="text"
                            placeholder="Search patterns..."
                            value={searchQuery}
                            onChange={e => setSearchQuery(e.target.value)}
                            className="pl-9 pr-4 py-2 rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 text-sm w-64"
                        />
                    </div>
                    <Button onClick={() => { setEditingRule(null); setShowCreateModal(true) }} className="bg-blue-600 hover:bg-blue-700 text-white text-sm">
                        <Plus className="w-4 h-4 mr-1" /> New Rule
                    </Button>
                    <Button variant="ghost" size="icon" onClick={fetchRules} title="Refresh">
                        <RefreshCw className="w-4 h-4 text-slate-400" />
                    </Button>
                </div>
            </div>

            {/* Table */}
            {loading ? (
                <div className="p-12 text-center text-slate-400">Loading rules...</div>
            ) : filteredRules.length === 0 ? (
                <div className="p-12 text-center bg-white rounded-xl border border-slate-200">
                    <Book className="w-12 h-12 mx-auto mb-3 text-slate-200" />
                    <p className="text-slate-500">No rules found. Create your first rule to get started.</p>
                </div>
            ) : (
                <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                            <thead className="bg-slate-50 text-slate-500 text-xs font-bold uppercase tracking-wider">
                                <tr>
                                    <th className="px-4 py-3">Source Pattern</th>
                                    <th className="px-4 py-3">Target Correction</th>
                                    <th className="px-4 py-3">Domain</th>
                                    <th className="px-4 py-3">Lang</th>
                                    <th className="px-4 py-3">Type</th>
                                    <th className="px-4 py-3">Strict</th>
                                    <th className="px-4 py-3">Confidence</th>
                                    <th className="px-4 py-3">Status</th>
                                    <th className="px-4 py-3 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {filteredRules.map(rule => (
                                    <tr key={rule.rule_id} className="hover:bg-slate-50/50 transition-colors group">
                                        <td className="px-4 py-3 font-mono text-xs text-slate-700 max-w-[200px] truncate" title={rule.source_pattern}>{rule.source_pattern}</td>
                                        <td className="px-4 py-3 font-mono text-xs text-blue-700 max-w-[200px] truncate" title={rule.target_correction}>{rule.target_correction}</td>
                                        <td className="px-4 py-3 text-xs text-slate-500">{rule.domain || "general"}</td>
                                        <td className="px-4 py-3 text-xs text-slate-500 font-mono">{rule.source_language || "—"} → {rule.target_language || "—"}</td>
                                        <td className="px-4 py-3">
                                            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${rule.is_regex ? "bg-purple-50 text-purple-700" : "bg-slate-100 text-slate-600"}`}>
                                                {rule.is_regex ? "regex" : "literal"}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 text-center">{rule.is_strict ? <Check className="w-4 h-4 text-green-600 mx-auto" /> : <span className="text-slate-300">—</span>}</td>
                                        <td className="px-4 py-3">
                                            <span className={`text-xs font-bold px-2 py-0.5 rounded ${rule.confidence_score >= 0.9 ? "bg-green-100 text-green-700" : rule.confidence_score >= 0.7 ? "bg-yellow-100 text-yellow-700" : "bg-slate-100 text-slate-600"}`}>
                                                {(rule.confidence_score * 100).toFixed(0)}%
                                            </span>
                                        </td>
                                        <td className="px-4 py-3">
                                            <span className={`text-[10px] font-bold uppercase px-2 py-1 rounded ${rule.status === "ACTIVE" ? "bg-green-50 text-green-700" : rule.status === "PENDING_APPROVAL" ? "bg-amber-50 text-amber-700" : "bg-red-50 text-red-600"}`}>
                                                {rule.status === "PENDING_APPROVAL" ? "PENDING" : rule.status}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3">
                                            <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                {rule.status === "PENDING_APPROVAL" && (
                                                    <>
                                                        <button onClick={() => handleApprove(rule.rule_id)} className="p-1.5 text-green-600 hover:bg-green-100 rounded" title="Approve">
                                                            <Check size={16} />
                                                        </button>
                                                        <button onClick={() => handleReject(rule.rule_id)} className="p-1.5 text-red-600 hover:bg-red-100 rounded" title="Reject">
                                                            <X size={16} />
                                                        </button>
                                                    </>
                                                )}
                                                <button onClick={() => { setEditingRule(rule); setShowCreateModal(true) }} className="p-1.5 text-slate-500 hover:bg-slate-100 rounded" title="Edit">
                                                    <Edit3 size={16} />
                                                </button>
                                                {deletingId === rule.rule_id ? (
                                                    <div className="flex items-center gap-1">
                                                        <button onClick={() => handleDelete(rule.rule_id)} className="px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700">Delete</button>
                                                        <button onClick={() => setDeletingId(null)} className="px-2 py-1 text-xs bg-slate-200 text-slate-600 rounded hover:bg-slate-300">Cancel</button>
                                                    </div>
                                                ) : (
                                                    <button onClick={() => setDeletingId(rule.rule_id)} className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded" title="Delete">
                                                        <Trash2 size={16} />
                                                    </button>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Create/Edit Modal */}
            {showCreateModal && (
                <RuleFormModal
                    rule={editingRule}
                    onClose={() => { setShowCreateModal(false); setEditingRule(null) }}
                    onSaved={() => { setShowCreateModal(false); setEditingRule(null); fetchRules() }}
                />
            )}
        </div>
    )
}

// ─── Rule Create/Edit Modal ──────────────────────────────────────────────────

function RuleFormModal({ rule, onClose, onSaved }: { rule: Rule | null; onClose: () => void; onSaved: () => void }) {
    const isEdit = !!rule
    const [form, setForm] = useState({
        source_pattern: rule?.source_pattern || "",
        target_correction: rule?.target_correction || "",
        context_tag: rule?.context_tag || "general",
        domain: rule?.domain || "general",
        source_language: rule?.source_language || "",
        target_language: rule?.target_language || "",
        is_regex: rule?.is_regex || false,
        is_strict: rule?.is_strict || false,
        priority: rule?.priority || 0,
        description: rule?.description || "",
        confidence_score: rule?.confidence_score ?? 1.0,
    })
    const [testSource, setTestSource] = useState("")
    const [testTarget, setTestTarget] = useState("")
    const [testResult, setTestResult] = useState<any>(null)
    const [saving, setSaving] = useState(false)
    const [testing, setTesting] = useState(false)
    const [error, setError] = useState("")

    const handleTest = async () => {
        if (!testSource) return
        setTesting(true)
        setTestResult(null)
        try {
            const result = await api.knowledge.testRule({
                source_pattern: form.source_pattern,
                target_correction: form.target_correction,
                is_regex: form.is_regex,
                test_source: testSource,
                test_target: testTarget,
            })
            setTestResult(result)
        } catch (e) {
            setError(getErrMessage(e))
        } finally {
            setTesting(false)
        }
    }

    const handleSave = async () => {
        if (!form.source_pattern || !form.target_correction) {
            setError("Source pattern and target correction are required.")
            return
        }
        setSaving(true)
        setError("")
        try {
            if (isEdit) {
                // PATCH to update all fields at once
                const token = typeof document !== 'undefined' ? document.cookie.match(/(^| )transmax_token=([^;]+)/)?.[2] : null
                const headers: Record<string, string> = { "Content-Type": "application/json" }
                if (token) headers["Authorization"] = `Bearer ${decodeURIComponent(token)}`
                const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"}/api/knowledge/rules/${rule!.rule_id}`, {
                    method: 'PATCH',
                    headers,
                    body: JSON.stringify(form),
                })
                if (!res.ok) {
                    const err = await res.json().catch(() => ({ detail: res.statusText }))
                    throw new Error(err.detail || `Update failed: ${res.status}`)
                }
            } else {
                await api.knowledge.createRule(form)
            }
            onSaved()
        } catch (e) {
            setError(getErrMessage(e))
        } finally {
            setSaving(false)
        }
    }

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
            <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto mx-4" onClick={e => e.stopPropagation()}>
                <div className="flex items-center justify-between p-6 border-b border-slate-100">
                    <h2 className="text-lg font-bold text-slate-900">{isEdit ? "Edit Rule" : "New Rule"}</h2>
                    <button onClick={onClose} className="p-1 hover:bg-slate-100 rounded"><X className="w-5 h-5 text-slate-400" /></button>
                </div>

                <div className="p-6 space-y-4">
                    {error && <div className="bg-red-50 text-red-700 text-sm p-3 rounded-lg flex items-center gap-2"><AlertTriangle className="w-4 h-4" /> {error}</div>}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label className="text-xs font-semibold text-slate-500 uppercase">Source Pattern *</label>
                            <input value={form.source_pattern} onChange={e => setForm(p => ({ ...p, source_pattern: e.target.value }))} className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono focus:ring-2 focus:ring-blue-500/20 focus:border-blue-300 outline-none" placeholder="e.g. Hypertension" />
                        </div>
                        <div>
                            <label className="text-xs font-semibold text-slate-500 uppercase">Target Correction *</label>
                            <input value={form.target_correction} onChange={e => setForm(p => ({ ...p, target_correction: e.target.value }))} className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono focus:ring-2 focus:ring-blue-500/20 focus:border-blue-300 outline-none" placeholder="e.g. Hypertension artérielle" />
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                            <label className="text-xs font-semibold text-slate-500 uppercase">Context Tag</label>
                            <input value={form.context_tag} onChange={e => setForm(p => ({ ...p, context_tag: e.target.value }))} className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-300 outline-none" />
                        </div>
                        <div>
                            <label className="text-xs font-semibold text-slate-500 uppercase">Domain</label>
                            <select value={form.domain} onChange={e => setForm(p => ({ ...p, domain: e.target.value }))} className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-300 outline-none">
                                {DOMAINS.map(d => <option key={d} value={d}>{d}</option>)}
                            </select>
                        </div>
                        <div>
                            <label className="text-xs font-semibold text-slate-500 uppercase">Priority</label>
                            <input type="number" value={form.priority} onChange={e => setForm(p => ({ ...p, priority: parseInt(e.target.value) || 0 }))} className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-300 outline-none" />
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label className="text-xs font-semibold text-slate-500 uppercase">Source Language</label>
                            <LanguageSelector value={form.source_language} onChange={v => setForm(p => ({ ...p, source_language: v }))} />
                        </div>
                        <div>
                            <label className="text-xs font-semibold text-slate-500 uppercase">Target Language</label>
                            <LanguageSelector value={form.target_language} onChange={v => setForm(p => ({ ...p, target_language: v }))} />
                        </div>
                    </div>

                    <div className="flex items-center gap-6">
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input type="checkbox" checked={form.is_regex} onChange={e => setForm(p => ({ ...p, is_regex: e.target.checked }))} className="rounded border-slate-300" />
                            <span className="text-sm text-slate-700">Regex pattern</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input type="checkbox" checked={form.is_strict} onChange={e => setForm(p => ({ ...p, is_strict: e.target.checked }))} className="rounded border-slate-300" />
                            <span className="text-sm text-slate-700">Strict mode</span>
                        </label>
                    </div>

                    <div>
                        <label className="text-xs font-semibold text-slate-500 uppercase">Description</label>
                        <textarea value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} rows={2} className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-300 outline-none resize-none" placeholder="Optional description..." />
                    </div>

                    {/* Test Sandbox */}
                    <div className="border border-slate-200 rounded-lg p-4 bg-slate-50/50">
                        <h3 className="text-sm font-bold text-slate-700 mb-3 flex items-center gap-2"><Play className="w-4 h-4" /> Test Rule</h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                            <div>
                                <label className="text-xs text-slate-500">Test Source Text</label>
                                <input value={testSource} onChange={e => setTestSource(e.target.value)} className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white focus:ring-2 focus:ring-blue-500/20 outline-none" placeholder="Enter source text..." />
                            </div>
                            <div>
                                <label className="text-xs text-slate-500">Test Target Text</label>
                                <input value={testTarget} onChange={e => setTestTarget(e.target.value)} className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white focus:ring-2 focus:ring-blue-500/20 outline-none" placeholder="Enter target text..." />
                            </div>
                        </div>
                        <Button onClick={handleTest} disabled={testing || !testSource} variant="outline" className="text-sm">
                            {testing ? "Testing..." : "Run Test"}
                        </Button>
                        {testResult && (
                            <div className={`mt-3 p-3 rounded-lg text-sm ${testResult.would_fire ? "bg-amber-50 border border-amber-200 text-amber-800" : "bg-green-50 border border-green-200 text-green-800"}`}>
                                <strong>{testResult.suggested_action}:</strong> Rule would {testResult.would_fire ? "fire" : "not fire"}.
                                {testResult.source_matches?.length > 0 && <span> Found {testResult.source_matches.length} match(es) in source.</span>}
                                {testResult.target_has_correction && <span> Target already contains correction.</span>}
                            </div>
                        )}
                    </div>
                </div>

                <div className="flex justify-end gap-3 p-6 border-t border-slate-100">
                    <Button variant="outline" onClick={onClose}>Cancel</Button>
                    <Button onClick={handleSave} disabled={saving} className="bg-blue-600 hover:bg-blue-700 text-white">
                        {saving ? "Saving..." : isEdit ? "Update Rule" : "Create Rule"}
                    </Button>
                </div>
            </div>
        </div>
    )
}

// ─── Tab 2: Glossaries ───────────────────────────────────────────────────────

function GlossariesTab() {
    const [glossaries, setGlossaries] = useState<Glossary[]>([])
    const [loading, setLoading] = useState(true)
    const [connectionError, setConnectionError] = useState<string | null>(null)
    const [expandedGlossary, setExpandedGlossary] = useState<string | null>(null)
    const [terms, setTerms] = useState<GlossaryTerm[]>([])
    const [termsLoading, setTermsLoading] = useState(false)
    const [showUpload, setShowUpload] = useState(false)
    const [searchQuery, setSearchQuery] = useState("")
    const [editingTermId, setEditingTermId] = useState<string | null>(null)
    const [editTargetText, setEditTargetText] = useState("")
    const [editIsForbidden, setEditIsForbidden] = useState(false)
    const [showAddTerm, setShowAddTerm] = useState(false)
    const [newTermSource, setNewTermSource] = useState("")
    const [newTermTarget, setNewTermTarget] = useState("")
    const [newTermForbidden, setNewTermForbidden] = useState(false)
    const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

    const fetchGlossaries = async () => {
        setLoading(true)
        setConnectionError(null)
        try {
            const data = await api.knowledge.listGlossaries()
            setGlossaries(data)
        } catch (e) {
            console.error("Failed to load glossaries:", e)
            setConnectionError(getErrMessage(e, "Failed to load glossaries"))
        }
        finally { setLoading(false) }
    }

    useEffect(() => { fetchGlossaries() }, [])

    const toggleExpand = async (gid: string, version: string) => {
        const key = `${gid}:${version}`
        if (expandedGlossary === key) {
            setExpandedGlossary(null)
            setShowAddTerm(false)
            setEditingTermId(null)
            return
        }
        setExpandedGlossary(key)
        setShowAddTerm(false)
        setEditingTermId(null)
        setTermsLoading(true)
        try {
            const data = await api.knowledge.getGlossaryTerms(gid, version)
            setTerms(data)
        } catch (e) { console.error("Failed to load terms:", e) }
        finally { setTermsLoading(false) }
    }

    const handleToggleActive = async (g: Glossary) => {
        try {
            await api.knowledge.updateGlossary(g.glossary_id, g.version, { is_active: !g.is_active })
            setGlossaries(prev => prev.map(gl =>
                gl.glossary_id === g.glossary_id && gl.version === g.version
                    ? { ...gl, is_active: !gl.is_active }
                    : gl
            ))
        } catch (e) { console.error("Failed to toggle glossary:", e) }
    }

    const handleDeleteGlossary = async (g: Glossary) => {
        try {
            await api.knowledge.deleteGlossary(g.glossary_id, g.version)
            setGlossaries(prev => prev.filter(gl => !(gl.glossary_id === g.glossary_id && gl.version === g.version)))
            setDeleteConfirm(null)
            if (expandedGlossary === `${g.glossary_id}:${g.version}`) setExpandedGlossary(null)
        } catch (e) { console.error("Failed to delete glossary:", e) }
    }

    const handleExport = async (g: Glossary) => {
        try {
            const blob = await api.knowledge.exportGlossary(g.glossary_id, g.version)
            const url = URL.createObjectURL(blob)
            const a = window.document.createElement("a")
            a.href = url
            a.download = `${g.glossary_id}_${g.version}.csv`
            window.document.body.appendChild(a)
            a.click()
            window.document.body.removeChild(a)
            URL.revokeObjectURL(url)
        } catch (e) { console.error("Failed to export glossary:", e) }
    }

    const handleAddTerm = async (gid: string, version: string) => {
        if (!newTermSource.trim() || !newTermTarget.trim()) return
        try {
            const result = await api.knowledge.addTerm(gid, version, {
                source_text: newTermSource, target_text: newTermTarget, is_forbidden: newTermForbidden
            })
            setTerms(prev => [...prev, result])
            setNewTermSource(""); setNewTermTarget(""); setNewTermForbidden(false); setShowAddTerm(false)
            // Update term count
            setGlossaries(prev => prev.map(gl =>
                gl.glossary_id === gid && gl.version === version
                    ? { ...gl, term_count: (gl.term_count || 0) + 1 }
                    : gl
            ))
        } catch (e) { console.error("Failed to add term:", e) }
    }

    const startEditTerm = (t: GlossaryTerm) => {
        setEditingTermId(t.term_id)
        setEditTargetText(t.target_text)
        setEditIsForbidden(t.is_forbidden)
    }

    const saveEditTerm = async (gid: string, version: string, termId: string) => {
        try {
            const result = await api.knowledge.updateTerm(gid, version, termId, {
                target_text: editTargetText, is_forbidden: editIsForbidden
            })
            setTerms(prev => prev.map(t => t.term_id === termId ? { ...t, ...result } : t))
            setEditingTermId(null)
        } catch (e) { console.error("Failed to update term:", e) }
    }

    const handleDeleteTerm = async (gid: string, version: string, termId: string) => {
        try {
            await api.knowledge.deleteTerm(gid, version, termId)
            setTerms(prev => prev.filter(t => t.term_id !== termId))
            setGlossaries(prev => prev.map(gl =>
                gl.glossary_id === gid && gl.version === version
                    ? { ...gl, term_count: Math.max(0, (gl.term_count || 1) - 1) }
                    : gl
            ))
        } catch (e) { console.error("Failed to delete term:", e) }
    }

    const filteredGlossaries = glossaries.filter(g =>
        !searchQuery || g.glossary_id.toLowerCase().includes(searchQuery.toLowerCase())
    )

    return (
        <div>
            {connectionError && (
                <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-xl flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0" />
                        <span className="text-sm text-red-700">{connectionError}</span>
                    </div>
                    <button onClick={fetchGlossaries} className="text-sm font-medium text-red-600 hover:text-red-800 flex items-center gap-1">
                        <RefreshCw className="w-3.5 h-3.5" /> Retry
                    </button>
                </div>
            )}
            <div className="flex items-center justify-between mb-4 gap-3">
                <div className="relative flex-1 max-w-xs">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <input
                        value={searchQuery}
                        onChange={e => setSearchQuery(e.target.value)}
                        placeholder="Search glossaries..."
                        className="w-full pl-9 pr-3 py-2 border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500/20"
                    />
                </div>
                <p className="text-sm text-slate-500">{filteredGlossaries.length} glossar{filteredGlossaries.length === 1 ? "y" : "ies"}</p>
                <Button onClick={() => setShowUpload(true)} className="bg-blue-600 hover:bg-blue-700 text-white text-sm">
                    <Upload className="w-4 h-4 mr-1" /> Upload Glossary
                </Button>
            </div>

            {loading ? (
                <div className="p-12 text-center text-slate-400">Loading glossaries...</div>
            ) : filteredGlossaries.length === 0 ? (
                <div className="p-12 text-center bg-white rounded-xl border border-slate-200">
                    <BookOpen className="w-12 h-12 mx-auto mb-3 text-slate-200" />
                    <p className="text-slate-500">{searchQuery ? "No glossaries match your search." : "No glossaries yet. Upload a CSV file to add one."}</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filteredGlossaries.map(g => {
                        const key = `${g.glossary_id}:${g.version}`
                        const isExpanded = expandedGlossary === key
                        const deleteKey = `${g.glossary_id}:${g.version}`
                        return (
                            <div key={key} className={`bg-white border rounded-xl shadow-sm transition-all ${isExpanded ? "col-span-full border-blue-200" : "border-slate-200 hover:shadow-md"}`}>
                                <div className="p-6 cursor-pointer" onClick={() => toggleExpand(g.glossary_id, g.version)}>
                                    <div className="flex justify-between items-start mb-3">
                                        <div className="p-3 bg-blue-50 rounded-lg"><BookOpen size={24} className="text-blue-600" /></div>
                                        <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
                                            {/* Active toggle switch */}
                                            <button
                                                onClick={() => handleToggleActive(g)}
                                                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${g.is_active ? "bg-green-500" : "bg-slate-300"}`}
                                                title={g.is_active ? "Deactivate" : "Activate"}
                                            >
                                                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${g.is_active ? "translate-x-6" : "translate-x-1"}`} />
                                            </button>
                                            {/* Export */}
                                            <button onClick={() => handleExport(g)} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-blue-600" title="Export CSV">
                                                <Download size={16} />
                                            </button>
                                            {/* Delete */}
                                            {deleteConfirm === deleteKey ? (
                                                <div className="flex items-center gap-1">
                                                    <button onClick={() => handleDeleteGlossary(g)} className="text-xs px-2 py-1 bg-red-600 text-white rounded hover:bg-red-700">Confirm</button>
                                                    <button onClick={() => setDeleteConfirm(null)} className="text-xs px-2 py-1 bg-slate-200 rounded hover:bg-slate-300">Cancel</button>
                                                </div>
                                            ) : (
                                                <button onClick={() => setDeleteConfirm(deleteKey)} className="p-1.5 rounded-lg hover:bg-red-50 text-slate-400 hover:text-red-600" title="Delete">
                                                    <Trash2 size={16} />
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                    <div className="font-bold text-lg text-slate-900 mb-1">{g.glossary_id}</div>
                                    <div className="text-xs text-slate-500 font-mono">
                                        ver {g.version} &bull; {g.term_count ?? "?"} terms &bull; Created {new Date(g.created_at).toLocaleDateString()}
                                    </div>
                                    {g.meta_json?.source_language && (
                                        <div className="text-xs text-slate-400 mt-1">{g.meta_json.source_language} &rarr; {g.meta_json.target_language}</div>
                                    )}
                                </div>
                                {isExpanded && (
                                    <div className="border-t border-slate-100 p-4">
                                        <div className="flex items-center justify-between mb-3">
                                            <span className="text-xs font-semibold text-slate-500 uppercase">Terms</span>
                                            <Button onClick={() => setShowAddTerm(!showAddTerm)} className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 h-7">
                                                <Plus className="w-3 h-3 mr-1" /> Add Term
                                            </Button>
                                        </div>

                                        {showAddTerm && (
                                            <div className="flex items-center gap-2 mb-3 p-2 bg-blue-50 rounded-lg">
                                                <input value={newTermSource} onChange={e => setNewTermSource(e.target.value)} placeholder="Source text" className="flex-1 px-2 py-1.5 border border-slate-200 rounded text-xs outline-none" />
                                                <input value={newTermTarget} onChange={e => setNewTermTarget(e.target.value)} placeholder="Target text" className="flex-1 px-2 py-1.5 border border-slate-200 rounded text-xs outline-none" />
                                                <label className="flex items-center gap-1 text-xs text-slate-600 whitespace-nowrap">
                                                    <input type="checkbox" checked={newTermForbidden} onChange={e => setNewTermForbidden(e.target.checked)} className="rounded" />
                                                    Forbidden
                                                </label>
                                                <button onClick={() => handleAddTerm(g.glossary_id, g.version)} className="px-2 py-1.5 bg-blue-600 text-white rounded text-xs hover:bg-blue-700">Save</button>
                                                <button onClick={() => setShowAddTerm(false)} className="px-2 py-1.5 bg-slate-200 rounded text-xs hover:bg-slate-300">Cancel</button>
                                            </div>
                                        )}

                                        {termsLoading ? (
                                            <div className="text-center text-sm text-slate-400 py-4">Loading terms...</div>
                                        ) : terms.length === 0 ? (
                                            <div className="text-center text-sm text-slate-400 py-4">No terms in this glossary.</div>
                                        ) : (
                                            <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
                                                <table className="w-full text-sm">
                                                    <thead className="bg-slate-50 text-xs text-slate-500 uppercase sticky top-0">
                                                        <tr>
                                                            <th className="px-3 py-2 text-left">Source</th>
                                                            <th className="px-3 py-2 text-left">Target</th>
                                                            <th className="px-3 py-2 text-center">Forbidden</th>
                                                            <th className="px-3 py-2 text-center w-24">Actions</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody className="divide-y divide-slate-50">
                                                        {terms.map(t => (
                                                            <tr key={t.term_id} className="hover:bg-slate-50 group">
                                                                <td className="px-3 py-2 font-mono text-xs">{t.source_text}</td>
                                                                <td className="px-3 py-2 font-mono text-xs text-blue-700">
                                                                    {editingTermId === t.term_id ? (
                                                                        <input
                                                                            value={editTargetText}
                                                                            onChange={e => setEditTargetText(e.target.value)}
                                                                            onKeyDown={e => e.key === "Enter" && saveEditTerm(g.glossary_id, g.version, t.term_id)}
                                                                            className="w-full px-1 py-0.5 border border-blue-300 rounded text-xs outline-none"
                                                                            autoFocus
                                                                        />
                                                                    ) : t.target_text}
                                                                </td>
                                                                <td className="px-3 py-2 text-center">
                                                                    {editingTermId === t.term_id ? (
                                                                        <input type="checkbox" checked={editIsForbidden} onChange={e => setEditIsForbidden(e.target.checked)} />
                                                                    ) : t.is_forbidden ? <AlertTriangle className="w-4 h-4 text-red-500 mx-auto" /> : "—"}
                                                                </td>
                                                                <td className="px-3 py-2 text-center">
                                                                    {editingTermId === t.term_id ? (
                                                                        <div className="flex items-center justify-center gap-1">
                                                                            <button onClick={() => saveEditTerm(g.glossary_id, g.version, t.term_id)} className="p-1 text-green-600 hover:bg-green-50 rounded"><Check size={14} /></button>
                                                                            <button onClick={() => setEditingTermId(null)} className="p-1 text-slate-400 hover:bg-slate-100 rounded"><X size={14} /></button>
                                                                        </div>
                                                                    ) : (
                                                                        <div className="flex items-center justify-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                                            <button onClick={() => startEditTerm(t)} className="p-1 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded" title="Edit"><Edit3 size={14} /></button>
                                                                            <button onClick={() => handleDeleteTerm(g.glossary_id, g.version, t.term_id)} className="p-1 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded" title="Delete"><Trash2 size={14} /></button>
                                                                        </div>
                                                                    )}
                                                                </td>
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        )
                    })}
                </div>
            )}

            {showUpload && <GlossaryUploadModal onClose={() => setShowUpload(false)} onUploaded={() => { setShowUpload(false); fetchGlossaries() }} />}
        </div>
    )
}

function GlossaryUploadModal({ onClose, onUploaded }: { onClose: () => void; onUploaded: () => void }) {
    const [file, setFile] = useState<File | null>(null)
    const [glossaryId, setGlossaryId] = useState("")
    const [version, setVersion] = useState("1.0.0")
    const [srcLang, setSrcLang] = useState("en")
    const [tgtLang, setTgtLang] = useState("fr")
    const [uploading, setUploading] = useState(false)
    const [error, setError] = useState("")

    const handleUpload = async () => {
        if (!file || !glossaryId) { setError("File and glossary ID are required."); return }
        setUploading(true)
        setError("")
        try {
            await api.knowledge.uploadGlossary(file, glossaryId, version, srcLang, tgtLang)
            onUploaded()
        } catch (e) { setError(getErrMessage(e)) }
        finally { setUploading(false) }
    }

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
            <div className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 p-6" onClick={e => e.stopPropagation()}>
                <h2 className="text-lg font-bold text-slate-900 mb-4">Upload Glossary</h2>
                {error && <div className="bg-red-50 text-red-700 text-sm p-3 rounded-lg mb-3">{error}</div>}
                <div className="bg-amber-50 text-amber-800 text-xs p-3 rounded-lg mb-3">
                    Re-uploading an existing glossary ID + version will replace all existing terms.
                </div>
                <div className="space-y-3">
                    <div>
                        <label className="text-xs font-semibold text-slate-500 uppercase">Glossary ID *</label>
                        <input value={glossaryId} onChange={e => setGlossaryId(e.target.value)} className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500/20" placeholder="e.g. fda-standard" />
                    </div>
                    <div>
                        <label className="text-xs font-semibold text-slate-500 uppercase">Version</label>
                        <input value={version} onChange={e => setVersion(e.target.value)} className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500/20" />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="text-xs font-semibold text-slate-500 uppercase">Source Lang</label>
                            <LanguageSelector value={srcLang} onChange={setSrcLang} />
                        </div>
                        <div>
                            <label className="text-xs font-semibold text-slate-500 uppercase">Target Lang</label>
                            <LanguageSelector value={tgtLang} onChange={setTgtLang} />
                        </div>
                    </div>
                    <div>
                        <label className="text-xs font-semibold text-slate-500 uppercase">CSV File *</label>
                        <input type="file" accept=".csv" onChange={e => setFile(e.target.files?.[0] || null)} className="w-full mt-1 text-sm" />
                    </div>
                </div>
                <div className="flex justify-end gap-3 mt-6">
                    <Button variant="outline" onClick={onClose}>Cancel</Button>
                    <Button onClick={handleUpload} disabled={uploading} className="bg-blue-600 hover:bg-blue-700 text-white">{uploading ? "Uploading..." : "Upload"}</Button>
                </div>
            </div>
        </div>
    )
}

// ─── Tab 3: Import / Export ──────────────────────────────────────────────────

function ImportExportTab() {
    // Import state
    const [importFile, setImportFile] = useState<File | null>(null)
    const [importing, setImporting] = useState(false)
    const [importResult, setImportResult] = useState<{ imported: number; skipped: number; errors: string[] } | null>(null)
    const [importError, setImportError] = useState("")
    const fileInputRef = useRef<HTMLInputElement>(null)
    const [dragActive, setDragActive] = useState(false)

    // Export state
    const [exportFormat, setExportFormat] = useState<"csv" | "json">("csv")
    const [exportDomain, setExportDomain] = useState("")
    const [exportStatus, setExportStatus] = useState("ACTIVE")
    const [exporting, setExporting] = useState(false)

    // Analytics state
    const [analytics, setAnalytics] = useState<AnalyticsEntry[]>([])
    const [analyticsLoading, setAnalyticsLoading] = useState(true)

    useEffect(() => {
        const fetchAnalytics = async () => {
            try {
                const data = await api.knowledge.getAnalytics()
                setAnalytics(data)
            } catch (e) { console.error("Analytics failed:", e) }
            finally { setAnalyticsLoading(false) }
        }
        fetchAnalytics()
    }, [])

    const handleImport = async () => {
        if (!importFile) return
        setImporting(true)
        setImportError("")
        setImportResult(null)
        try {
            const result = await api.knowledge.importRules(importFile)
            setImportResult(result)
            setImportFile(null)
        } catch (e) { setImportError(getErrMessage(e)) }
        finally { setImporting(false) }
    }

    const handleExport = async () => {
        setExporting(true)
        try {
            const blob = await api.knowledge.exportRules(exportFormat, exportDomain || undefined, exportStatus || undefined)
            const url = URL.createObjectURL(blob)
            const a = document.createElement("a")
            a.href = url
            a.download = `blackbook_rules.${exportFormat}`
            document.body.appendChild(a)
            a.click()
            document.body.removeChild(a)
            URL.revokeObjectURL(url)
        } catch (e) { console.error("Export failed:", e) }
        finally { setExporting(false) }
    }

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault()
        setDragActive(false)
        const file = e.dataTransfer.files?.[0]
        if (file && (file.name.endsWith('.csv') || file.name.endsWith('.json'))) {
            setImportFile(file)
        }
    }

    return (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Import */}
            <GlassCard>
                <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2"><Upload className="w-5 h-5 text-blue-600" /> Import Rules</h3>
                <div
                    className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${dragActive ? "border-blue-400 bg-blue-50" : "border-slate-200 bg-slate-50/50"}`}
                    onDragOver={e => { e.preventDefault(); setDragActive(true) }}
                    onDragLeave={() => setDragActive(false)}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                >
                    <Upload className="w-8 h-8 text-slate-300 mx-auto mb-3" />
                    {importFile ? (
                        <p className="text-sm text-blue-700 font-medium">{importFile.name}</p>
                    ) : (
                        <>
                            <p className="text-sm text-slate-500">Drag & drop a CSV or JSON file here</p>
                            <p className="text-xs text-slate-400 mt-1">or click to browse</p>
                        </>
                    )}
                    <input ref={fileInputRef} type="file" accept=".csv,.json" className="hidden" onChange={e => setImportFile(e.target.files?.[0] || null)} />
                </div>
                {importFile && (
                    <Button onClick={handleImport} disabled={importing} className="mt-4 w-full bg-blue-600 hover:bg-blue-700 text-white">
                        {importing ? "Importing..." : `Import ${importFile.name}`}
                    </Button>
                )}
                {importError && <div className="mt-3 bg-red-50 text-red-700 text-sm p-3 rounded-lg">{importError}</div>}
                {importResult && (
                    <div className="mt-3 bg-green-50 border border-green-200 text-green-800 text-sm p-3 rounded-lg">
                        <strong>{importResult.imported}</strong> imported, <strong>{importResult.skipped}</strong> skipped.
                        {importResult.errors.length > 0 && (
                            <details className="mt-2">
                                <summary className="cursor-pointer text-xs text-red-600">{importResult.errors.length} error(s)</summary>
                                <ul className="mt-1 text-xs text-red-600 list-disc list-inside">{importResult.errors.map((e, i) => <li key={i}>{e}</li>)}</ul>
                            </details>
                        )}
                    </div>
                )}
            </GlassCard>

            {/* Export */}
            <GlassCard>
                <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2"><Download className="w-5 h-5 text-green-600" /> Export Rules</h3>
                <div className="space-y-3">
                    <div>
                        <label className="text-xs font-semibold text-slate-500 uppercase">Format</label>
                        <div className="flex gap-2 mt-1">
                            {(["csv", "json"] as const).map(f => (
                                <button key={f} onClick={() => setExportFormat(f)} className={`px-4 py-2 text-sm font-medium rounded-lg transition-all ${exportFormat === f ? "bg-slate-800 text-white" : "bg-slate-100 text-slate-500 hover:bg-slate-200"}`}>
                                    {f.toUpperCase()}
                                </button>
                            ))}
                        </div>
                    </div>
                    <div>
                        <label className="text-xs font-semibold text-slate-500 uppercase">Domain Filter</label>
                        <select value={exportDomain} onChange={e => setExportDomain(e.target.value)} className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white outline-none">
                            <option value="">All Domains</option>
                            {DOMAINS.map(d => <option key={d} value={d}>{d}</option>)}
                        </select>
                    </div>
                    <div>
                        <label className="text-xs font-semibold text-slate-500 uppercase">Status Filter</label>
                        <select value={exportStatus} onChange={e => setExportStatus(e.target.value)} className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white outline-none">
                            <option value="ACTIVE">Active</option>
                            <option value="PENDING_APPROVAL">Pending</option>
                            <option value="">All</option>
                        </select>
                    </div>
                    <Button onClick={handleExport} disabled={exporting} className="w-full bg-green-600 hover:bg-green-700 text-white mt-2">
                        {exporting ? "Exporting..." : `Download ${exportFormat.toUpperCase()}`}
                    </Button>
                </div>
            </GlassCard>

            {/* Analytics */}
            <GlassCard className="lg:col-span-2">
                <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2"><BarChart3 className="w-5 h-5 text-purple-600" /> Rule Analytics</h3>
                {analyticsLoading ? (
                    <div className="text-center text-sm text-slate-400 py-8">Loading analytics...</div>
                ) : analytics.length === 0 ? (
                    <div className="text-center text-sm text-slate-400 py-8">No analytics data yet. Rules need to fire during translations to generate data.</div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
                                <tr>
                                    <th className="px-4 py-3 text-left">Source Pattern</th>
                                    <th className="px-4 py-3 text-right">Fire Count</th>
                                    <th className="px-4 py-3 text-right">False Positives</th>
                                    <th className="px-4 py-3 text-right">Effectiveness</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {analytics.map(a => (
                                    <tr key={a.rule_id} className="hover:bg-slate-50">
                                        <td className="px-4 py-3 font-mono text-xs">{a.source_pattern}</td>
                                        <td className="px-4 py-3 text-right font-bold text-slate-700">{a.fire_count}</td>
                                        <td className="px-4 py-3 text-right text-red-600">{a.false_positive_count}</td>
                                        <td className="px-4 py-3 text-right">
                                            <span className={`font-bold ${a.effectiveness >= 90 ? "text-green-600" : a.effectiveness >= 70 ? "text-yellow-600" : "text-red-600"}`}>
                                                {a.effectiveness.toFixed(1)}%
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </GlassCard>
        </div>
    )
}
