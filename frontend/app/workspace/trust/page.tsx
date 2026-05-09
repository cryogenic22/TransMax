"use client"

import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import { Shield, Book, BookOpen, Lock, CheckCircle, XCircle, AlertTriangle, RefreshCw } from "lucide-react"
import { GlassCard } from "@/components/ui/GlassCard"
import { api } from "@/lib/api"

export default function TrustCenterPage() {
    const [activeTab, setActiveTab] = useState("rules")

    return (
        <div className="space-y-8">
            {/* Header */}
            <div>
                <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-indigo-600">
                    Trust Center
                </h1>
                <p className="text-gray-500 mt-2">
                    Manage the AI&apos;s knowledge, enforce compliance, and verify privacy settings.
                </p>
            </div>

            {/* Navigation Tabs */}
            <div className="flex gap-4 border-b border-gray-200 pb-2">
                <button
                    onClick={() => setActiveTab("rules")}
                    className={`pb-2 px-4 transition-all ${activeTab === "rules"
                            ? "border-b-2 border-blue-600 text-blue-600 font-semibold"
                            : "text-gray-500 hover:text-gray-900"
                        }`}
                >
                    <span className="flex items-center gap-2">
                        <Book size={18} />
                        Black Book (Rules)
                    </span>
                </button>
                <button
                    onClick={() => setActiveTab("glossary")}
                    className={`pb-2 px-4 transition-all ${activeTab === "glossary"
                            ? "border-b-2 border-blue-600 text-blue-600 font-semibold"
                            : "text-gray-500 hover:text-gray-900"
                        }`}
                >
                    <span className="flex items-center gap-2">
                        <BookOpen size={18} />
                        Glossaries
                    </span>
                </button>
                <button
                    onClick={() => setActiveTab("privacy")}
                    className={`pb-2 px-4 transition-all ${activeTab === "privacy"
                            ? "border-b-2 border-blue-600 text-blue-600 font-semibold"
                            : "text-gray-500 hover:text-gray-900"
                        }`}
                >
                    <span className="flex items-center gap-2">
                        <Shield size={18} />
                        Privacy & Safety
                    </span>
                </button>
            </div>

            {/* Content Area */}
            <div className="min-h-[500px]">
                {activeTab === "rules" && <BlackBookView />}
                {activeTab === "glossary" && <GlossaryView />}
                {activeTab === "privacy" && <PrivacyMonitor />}
            </div>
        </div>
    )
}

function BlackBookView() {
    const [rules, setRules] = useState<any[]>([])
    const [loading, setLoading] = useState(true)

    const fetchRules = async () => {
        setLoading(true)
        try {
            const data = await api.knowledge.listRules()
            setRules(data)
        } catch (e) {
            console.error("Failed to fetch rules", e)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchRules()
    }, [])

    const handleVote = async (id: string, status: "ACTIVE" | "REJECTED") => {
        await api.knowledge.updateRule(id, status)
        fetchRules()
    }

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <h2 className="text-xl font-semibold">Learned Translation Rules</h2>
                <button onClick={fetchRules} className="btn btn-secondary text-sm">
                    <RefreshCw size={14} className="mr-2" /> Refresh
                </button>
            </div>

            <GlassCard>
                {loading ? (
                    <div className="p-8 text-center text-gray-500">Loading rules...</div>
                ) : rules.length === 0 ? (
                    <div className="p-12 text-center">
                        <div className="bg-gray-100 rounded-full w-16 h-16 flex items-center justify-center mx-auto mb-4">
                            <CheckCircle className="text-green-500" size={32} />
                        </div>
                        <h3 className="text-lg font-medium">No Pending Rules</h3>
                        <p className="text-gray-500 mt-1">
                            The Black Book is currently up to date. Make corrections in the Editor to teach the AI new rules.
                        </p>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left">
                            <thead className="bg-gray-50 text-gray-600 text-sm">
                                <tr>
                                    <th className="p-4 rounded-tl-lg">Source Pattern</th>
                                    <th className="p-4">Target Correction</th>
                                    <th className="p-4">Confidence</th>
                                    <th className="p-4">Status</th>
                                    <th className="p-4 rounded-tr-lg text-right">Action</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {rules.map((rule) => (
                                    <tr key={rule.rule_id} className="hover:bg-gray-50 transition-colors">
                                        <td className="p-4 font-mono text-sm text-gray-800">{rule.source_pattern}</td>
                                        <td className="p-4 font-mono text-sm text-blue-700">{rule.target_correction}</td>
                                        <td className="p-4">
                                            <span
                                                className={`px-2 py-1 rounded-full text-xs font-medium ${rule.confidence_score > 0.9
                                                        ? "bg-green-100 text-green-700"
                                                        : rule.confidence_score > 0.7
                                                            ? "bg-yellow-100 text-yellow-700"
                                                            : "bg-gray-100 text-gray-600"
                                                    }`}
                                            >
                                                {(rule.confidence_score * 100).toFixed(0)}%
                                            </span>
                                        </td>
                                        <td className="p-4">
                                            <span className="text-xs font-semibold text-gray-500">{rule.status}</span>
                                        </td>
                                        <td className="p-4 text-right space-x-2">
                                            {rule.status === "PENDING_APPROVAL" && (
                                                <>
                                                    <button
                                                        onClick={() => handleVote(rule.rule_id, "ACTIVE")}
                                                        className="p-1 text-green-600 hover:bg-green-50 rounded"
                                                        title="Approve"
                                                    >
                                                        <CheckCircle size={18} />
                                                    </button>
                                                    <button
                                                        onClick={() => handleVote(rule.rule_id, "REJECTED")}
                                                        className="p-1 text-red-600 hover:bg-red-50 rounded"
                                                        title="Reject"
                                                    >
                                                        <XCircle size={18} />
                                                    </button>
                                                </>
                                            )}
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

function GlossaryView() {
    return (
        <GlassCard className="p-8 text-center">
            <BookOpen className="w-12 h-12 text-blue-500 mx-auto mb-4" />
            <h3 className="text-lg font-semibold">Regulatory Glossaries</h3>
            <p className="text-gray-500 mb-6 max-w-md mx-auto">
                Manage mandated terminology dictionaries (FDA, EMA, PMDA).
                Currently 3 Global Glossaries are active.
            </p>
            {/* Mock for now */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-left">
                <div className="border border-gray-200 p-4 rounded-lg">
                    <div className="font-semibold">FDA Standard Terms</div>
                    <div className="text-xs text-gray-500">ver 2024.1 • 14,203 terms</div>
                    <div className="mt-2 text-green-600 text-xs font-medium flex items-center gap-1">
                        <CheckCircle size={12} /> Active
                    </div>
                </div>
                <div className="border border-gray-200 p-4 rounded-lg">
                    <div className="font-semibold">EMA MedDRA (EU)</div>
                    <div className="text-xs text-gray-500">ver 27.1 • 8,100 terms</div>
                    <div className="mt-2 text-green-600 text-xs font-medium flex items-center gap-1">
                        <CheckCircle size={12} /> Active
                    </div>
                </div>
                <div className="border border-gray-200 p-4 rounded-lg">
                    <div className="font-semibold">TransMax Exclusion List</div>
                    <div className="text-xs text-gray-500">ver internal.4 • 150 terms</div>
                    <div className="mt-2 text-green-600 text-xs font-medium flex items-center gap-1">
                        <CheckCircle size={12} /> Active
                    </div>
                </div>
            </div>
        </GlassCard>
    )
}

function PrivacyMonitor() {
    return (
        <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <GlassCard className="p-6 border-l-4 border-l-green-500">
                    <h3 className="font-semibold flex items-center gap-2 mb-2">
                        <Lock className="text-green-600" size={20} />
                        Zero Retention (Azure OpenAI)
                    </h3>
                    <p className="text-sm text-gray-600 mb-4">
                        Data passed to the LLM is <strong>not stored</strong> or used for training models.
                        This is enforced via API policy `opt-out: true`.
                    </p>
                    <div className="flex items-center gap-2 text-xs font-mono bg-gray-100 p-2 rounded">
                        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
                        Policy Active: NO_STORE
                    </div>
                </GlassCard>

                <GlassCard className="p-6 border-l-4 border-l-blue-500">
                    <h3 className="font-semibold flex items-center gap-2 mb-2">
                        <Shield className="text-blue-600" size={20} />
                        PII Redaction Shield
                    </h3>
                    <p className="text-sm text-gray-600 mb-4">
                        Personally Identifiable Information (Names, Dates, MRNs) is masked
                        <strong> before</strong> leaving the secure perimeter.
                    </p>
                    <div className="flex items-center gap-2 text-xs font-mono bg-gray-100 p-2 rounded">
                        <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></div>
                        Scrubber Active: NER_V2_EN
                    </div>
                </GlassCard>
            </div>

            <GlassCard className="p-6">
                <h3 className="font-semibold mb-4">Privacy Impact Assessment</h3>
                <div className="space-y-4">
                    <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
                        <span className="text-sm font-medium">Data Residency</span>
                        <span className="text-sm text-gray-600">US-EAST-2 (Virginia)</span>
                    </div>
                    <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
                        <span className="text-sm font-medium">Encryption at Rest</span>
                        <span className="text-sm text-green-600 flex items-center gap-1">
                            <CheckCircle size={14} /> AES-256
                        </span>
                    </div>
                    <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
                        <span className="text-sm font-medium">Audit Trail Immutability</span>
                        <span className="text-sm text-green-600 flex items-center gap-1">
                            <CheckCircle size={14} /> SHA-256 Chained
                        </span>
                    </div>
                </div>
            </GlassCard>
        </div>
    )
}
