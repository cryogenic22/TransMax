"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { ArrowLeft, Check, ChevronRight, FileText, Upload, Shield, Building2, Package } from "lucide-react"
import { Button } from "@/components/ui/button"
import { GlassCard } from "@/components/ui/GlassCard"
import { MOCK_CLIENTS, type Protocol, type ClientProfile } from "@/lib/protocols"

// Steps
const STEPS = [
    { id: 1, label: "Protocol Selection" },
    { id: 2, label: "Document Ingestion" },
    { id: 3, label: "Validation & Launch" }
]

export default function NewJobPage() {
    const router = useRouter()
    const [currentStep, setCurrentStep] = useState(1)

    // Selection State
    const [selectedClient, setSelectedClient] = useState<ClientProfile | null>(null)
    const [selectedProduct, setSelectedProduct] = useState<ClientProfile['products'][0] | null>(null)
    const [selectedProtocol, setSelectedProtocol] = useState<Protocol | null>(null)
    const [file, setFile] = useState<File | null>(null)
    const [isSubmitting, setIsSubmitting] = useState(false)

    // Handlers
    // Handlers
    const handleLaunch = async () => {
        if (!selectedClient || !selectedProduct || !selectedProtocol || !file) return

        setIsSubmitting(true)
        try {
            // For now, just navigate to workspace - in production would upload file first
            // then call api.documents.translate() or api.jobs.create()
            console.log("Launching job with:", {
                client: selectedClient,
                product: selectedProduct,
                protocol: selectedProtocol,
                file: file.name
            })
            router.push('/workspace')
        } catch (e) {
            console.error(e)
            alert("Failed to initiate protocol. Is the backend running?")
            setIsSubmitting(false)
        }
    }

    return (
        <main className="min-h-screen bg-slate-50 font-sans pb-20">
            {/* Header */}
            <header className="bg-white border-b border-slate-200 sticky top-0 z-40">
                <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
                    <Button variant="ghost" size="sm" onClick={() => router.push("/workspace")} className="text-slate-500">
                        <ArrowLeft className="w-4 h-4 mr-2" /> Cancel
                    </Button>
                    <div className="flex items-center gap-8">
                        {STEPS.map((step) => (
                            <div key={step.id} className="flex items-center gap-2">
                                <div className={`
                                    w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center transition-colors
                                    ${currentStep >= step.id ? 'bg-primary text-white' : 'bg-slate-100 text-slate-400'}
                                `}>
                                    {currentStep > step.id ? <Check className="w-3 h-3" /> : step.id}
                                </div>
                                <span className={`text-sm font-medium ${currentStep >= step.id ? 'text-slate-900' : 'text-slate-400'}`}>
                                    {step.label}
                                </span>
                            </div>
                        ))}
                    </div>
                    <div className="w-20" /> {/* Spacer */}
                </div>
            </header>

            <div className="max-w-3xl mx-auto px-6 py-12">
                <AnimatePresence mode="wait">
                    {/* STEP 1: PROTOCOL SELECTION */}
                    {currentStep === 1 && (
                        <motion.div
                            key="step1"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            className="space-y-8"
                        >
                            <div className="text-center mb-8">
                                <h2 className="text-2xl font-bold text-slate-900">Initiate Translation Protocol</h2>
                                <p className="text-slate-500 mt-2">Select the Client and Product to load the approved governance framework.</p>
                            </div>

                            {/* Client Grid */}
                            <div className="grid grid-cols-2 gap-4">
                                {MOCK_CLIENTS.map(client => (
                                    <div
                                        key={client.id}
                                        onClick={() => { setSelectedClient(client); setSelectedProduct(null); setSelectedProtocol(null); }}
                                        className={`
                                            p-4 rounded-xl bordercursor-pointer transition-all flex items-center gap-4
                                            ${selectedClient?.id === client.id
                                                ? 'border-primary ring-1 ring-primary bg-blue-50/50'
                                                : 'border-slate-200 bg-white hover:border-blue-300 hover:shadow-sm'}
                                        `}
                                    >
                                        <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center text-slate-500">
                                            <Building2 className="w-5 h-5" />
                                        </div>
                                        <div>
                                            <div className="font-semibold text-slate-800">{client.name}</div>
                                            <div className="text-xs text-slate-500">{client.products.length} Products</div>
                                        </div>
                                    </div>
                                ))}
                            </div>

                            {/* Product & Protocol (Conditional) */}
                            {selectedClient && (
                                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
                                    <div>
                                        <label className="text-xs font-bold uppercase text-slate-400 mb-2 block">Product Line</label>
                                        <div className="flex flex-wrap gap-3">
                                            {selectedClient.products.map(prod => (
                                                <button
                                                    key={prod.id}
                                                    onClick={() => { setSelectedProduct(prod); setSelectedProtocol(null); }}
                                                    className={`
                                                        px-4 py-2 rounded-lg text-sm font-medium border transition-colors flex items-center gap-2
                                                        ${selectedProduct?.id === prod.id
                                                            ? 'bg-slate-800 text-white border-slate-800'
                                                            : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'}
                                                    `}
                                                >
                                                    <Package className="w-4 h-4" /> {prod.name}
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    {selectedProduct && (
                                        <div>
                                            <label className="text-xs font-bold uppercase text-slate-400 mb-2 block">Available Protocols</label>
                                            <div className="grid grid-cols-1 gap-3">
                                                {selectedProduct.protocols.length === 0 ? (
                                                    <div className="text-slate-400 italic text-sm p-4 border rounded bg-slate-50">No active protocols found for this product.</div>
                                                ) : (
                                                    selectedProduct.protocols.map(proto => (
                                                        <div
                                                            key={proto.id}
                                                            onClick={() => setSelectedProtocol(proto)}
                                                            className={`
                                                                p-4 rounded-lg border text-left transition-all cursor-pointer relative overflow-hidden
                                                                ${selectedProtocol?.id === proto.id
                                                                    ? 'border-primary bg-primary/5'
                                                                    : 'border-slate-200 bg-white hover:border-blue-300'}
                                                            `}
                                                        >
                                                            <div className="flex justify-between items-start mb-1">
                                                                <span className="font-bold text-slate-800 block">{proto.name}</span>
                                                                {selectedProtocol?.id === proto.id && <Check className="w-5 h-5 text-primary" />}
                                                            </div>
                                                            <p className="text-sm text-slate-500 mb-3">{proto.description}</p>
                                                            <div className="flex flex-wrap gap-2 text-xs">
                                                                <span className="px-2 py-1 rounded bg-slate-100 text-slate-600 font-mono">
                                                                    {proto.archetype}
                                                                </span>
                                                                <span className={`px-2 py-1 rounded font-mono ${proto.tier === 'TIER_A' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600'}`}>
                                                                    {proto.tier}
                                                                </span>
                                                                <span className="px-2 py-1 rounded bg-blue-50 text-blue-700">
                                                                    {proto.target_languages.join(", ").toUpperCase()}
                                                                </span>
                                                            </div>
                                                        </div>
                                                    ))
                                                )}
                                            </div>
                                        </div>
                                    )}
                                </motion.div>
                            )}

                            <div className="flex justify-end pt-8">
                                <Button
                                    onClick={() => setCurrentStep(2)}
                                    disabled={!selectedProtocol}
                                    className="bg-primary hover:bg-blue-800 text-white gap-2"
                                >
                                    Continue to Upload <ChevronRight className="w-4 h-4" />
                                </Button>
                            </div>
                        </motion.div>
                    )}

                    {/* STEP 2: DOCUMENT INGESTION */}
                    {currentStep === 2 && (
                        <motion.div
                            key="step2"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            className="space-y-8"
                        >
                            <div className="text-center mb-8">
                                <h2 className="text-2xl font-bold text-slate-900">Secure Ingestion</h2>
                                <p className="text-slate-500 mt-2">Upload the source dossier. Allowed: PDF, DOCX (Sanitized).</p>
                            </div>

                            <GlassCard className="border-dashed border-2 border-slate-300 bg-slate-50 min-h-[300px] flex flex-col items-center justify-center cursor-pointer hover:border-primary hover:bg-blue-50/10 transition-colors">
                                <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center shadow-sm mb-4">
                                    <Upload className="w-8 h-8 text-primary" />
                                </div>
                                <h3 className="text-lg font-semibold text-slate-700 mb-1">Drag file here or click to browse</h3>
                                <p className="text-sm text-slate-400 mb-6">Max File Size: 50MB</p>
                                <Button variant="outline" onClick={() => setFile(new File(["foo"], "protocol_v1.docx"))}>
                                    Select File (Simulate)
                                </Button>
                            </GlassCard>

                            {file && (
                                <div className="flex items-center gap-4 p-4 bg-white border border-green-200 rounded-lg shadow-sm">
                                    <div className="w-10 h-10 bg-green-100 rounded flex items-center justify-center text-green-600">
                                        <FileText className="w-5 h-5" />
                                    </div>
                                    <div className="flex-1">
                                        <div className="font-semibold text-slate-800">{file.name}</div>
                                        <div className="text-xs text-slate-500">Ready for Analysis</div>
                                    </div>
                                    <Check className="w-5 h-5 text-green-500" />
                                </div>
                            )}

                            <div className="flex justify-between pt-8">
                                <Button variant="ghost" onClick={() => setCurrentStep(1)}>Back</Button>
                                <Button
                                    onClick={() => setCurrentStep(3)}
                                    disabled={!file}
                                    className="bg-primary hover:bg-blue-800 text-white gap-2"
                                >
                                    Proceed to Validation <ChevronRight className="w-4 h-4" />
                                </Button>
                            </div>
                        </motion.div>
                    )}

                    {/* STEP 3: LAUNCH SUMMARY */}
                    {currentStep === 3 && selectedProtocol && (
                        <motion.div
                            key="step3"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            className="space-y-8"
                        >
                            <div className="text-center mb-8">
                                <h2 className="text-2xl font-bold text-slate-900">Confirm Protocol Initiation</h2>
                                <p className="text-slate-500 mt-2">Review parameters before locking the governance chain.</p>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <GlassCard>
                                    <div className="text-xs font-bold uppercase text-slate-400 mb-4">Target Configuration</div>
                                    <div className="space-y-4">
                                        <div>
                                            <div className="text-sm text-slate-500">Client / Product</div>
                                            <div className="font-semibold text-slate-800">{selectedClient?.name} / {selectedProduct?.name}</div>
                                        </div>
                                        <div>
                                            <div className="text-sm text-slate-500">Protocol</div>
                                            <div className="font-semibold text-primary">{selectedProtocol.name}</div>
                                        </div>
                                        <div>
                                            <div className="text-sm text-slate-500">Languages</div>
                                            <div className="font-mono text-sm bg-slate-100 inline-block px-2 py-1 rounded mt-1">
                                                {selectedProtocol.target_languages.join(" → ").toUpperCase()}
                                            </div>
                                        </div>
                                    </div>
                                </GlassCard>

                                <GlassCard>
                                    <div className="text-xs font-bold uppercase text-slate-400 mb-4">Governance Profile</div>
                                    <div className="space-y-3">
                                        <div className="flex justify-between items-center py-2 border-b border-slate-50">
                                            <span className="text-sm text-slate-600">Archetype</span>
                                            <span className="font-mono text-xs bg-slate-100 px-2 py-1 rounded">{selectedProtocol.archetype}</span>
                                        </div>
                                        <div className="flex justify-between items-center py-2 border-b border-slate-50">
                                            <span className="text-sm text-slate-600">Risk Tier</span>
                                            <span className="font-mono text-xs bg-amber-50 text-amber-700 px-2 py-1 rounded">{selectedProtocol.tier}</span>
                                        </div>
                                        <div className="pt-2">
                                            <span className="text-sm text-slate-600 block mb-2">Active Gates:</span>
                                            <div className="flex flex-wrap gap-2">
                                                {selectedProtocol.governance_features.map(f => (
                                                    <span key={f} className="text-[10px] font-bold uppercase bg-blue-50 text-blue-600 px-2 py-1 rounded border border-blue-100 flex items-center gap-1">
                                                        <Shield className="w-3 h-3" /> {f}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                </GlassCard>
                            </div>

                            <div className="flex justify-between pt-8">
                                <Button variant="ghost" onClick={() => setCurrentStep(2)}>Back</Button>
                                <Button
                                    onClick={handleLaunch}
                                    disabled={isSubmitting}
                                    className="bg-green-600 hover:bg-green-700 text-white min-w-[200px] shadow-lg shadow-green-200"
                                >
                                    {isSubmitting ? "Initializing..." : "Authorize & Launch Agent"}
                                </Button>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </main>
    )
}
