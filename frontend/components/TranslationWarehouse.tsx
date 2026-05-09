"use client"

import { useState, useEffect } from "react"
import { CheckCircle2, AlertTriangle, Loader2, Package, Brain, Shield, Sparkles } from "lucide-react"

/**
 * TranslationWarehouse - Light-themed visualization connected to real backend progress
 * Shows segments flowing through batches → LLM processing → Quality Gates → Complete
 */

interface Batch {
    id: number
    segmentCount: number
    status: "pending" | "processing" | "complete" | "failed"
}

interface TranslationWarehouseProps {
    totalSegments: number
    translatedCount: number
    isActive: boolean
    currentPhase: "batching" | "translating" | "quality" | "complete"
}

export default function TranslationWarehouse({
    totalSegments,
    translatedCount,
    isActive,
    currentPhase
}: TranslationWarehouseProps) {
    const [batches, setBatches] = useState<Batch[]>([])

    // Create batches based on segment count
    useEffect(() => {
        if (!isActive || totalSegments === 0) return

        const BATCH_SIZE = 5
        const batchCount = Math.ceil(totalSegments / BATCH_SIZE)

        const newBatches: Batch[] = Array.from({ length: batchCount }, (_, i) => ({
            id: i,
            segmentCount: Math.min(BATCH_SIZE, totalSegments - i * BATCH_SIZE),
            status: "pending" as const
        }))

        setBatches(newBatches)
    }, [isActive, totalSegments])

    // Update batch statuses based on real progress
    useEffect(() => {
        if (!batches.length) return

        const BATCH_SIZE = 5
        const completedBatches = Math.floor(translatedCount / BATCH_SIZE)
        const currentBatchProgress = translatedCount % BATCH_SIZE

        setBatches(prev => prev.map((batch, idx) => {
            if (idx < completedBatches) {
                return { ...batch, status: "complete" as const }
            } else if (idx === completedBatches && currentBatchProgress > 0) {
                return { ...batch, status: "processing" as const }
            } else if (idx <= completedBatches + 3) {
                return { ...batch, status: "processing" as const }
            }
            return { ...batch, status: "pending" as const }
        }))
    }, [translatedCount, batches.length])

    const progressPercent = totalSegments > 0
        ? Math.round((translatedCount / totalSegments) * 100)
        : 0

    const pendingCount = batches.filter(b => b.status === "pending").length
    const processingCount = batches.filter(b => b.status === "processing").length
    const completeCount = batches.filter(b => b.status === "complete").length

    return (
        <div style={{
            background: "white",
            borderRadius: "16px",
            padding: "2rem",
            border: "1px solid #e5e7eb",
            boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)"
        }}>
            {/* Header */}
            <div style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "1.5rem"
            }}>
                <div>
                    <h2 style={{
                        fontSize: "1.25rem",
                        fontWeight: 600,
                        margin: 0,
                        color: "#1f2937",
                        display: "flex",
                        alignItems: "center",
                        gap: "0.5rem"
                    }}>
                        <Sparkles size={20} style={{ color: "#f59e0b" }} />
                        Agentic Translation Pipeline
                    </h2>
                    <p style={{ color: "#6b7280", margin: "0.25rem 0 0", fontSize: "0.875rem" }}>
                        AI agents processing {totalSegments} segments in parallel
                    </p>
                </div>

                {/* Progress Ring */}
                <div style={{ position: "relative", width: "64px", height: "64px" }}>
                    <svg viewBox="0 0 100 100" style={{ transform: "rotate(-90deg)" }}>
                        <circle
                            cx="50" cy="50" r="42"
                            fill="none"
                            stroke="#e5e7eb"
                            strokeWidth="8"
                        />
                        <circle
                            cx="50" cy="50" r="42"
                            fill="none"
                            stroke="#3b82f6"
                            strokeWidth="8"
                            strokeDasharray={`${progressPercent * 2.64} 264`}
                            strokeLinecap="round"
                            style={{ transition: "stroke-dasharray 0.5s ease" }}
                        />
                    </svg>
                    <div style={{
                        position: "absolute",
                        inset: 0,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center"
                    }}>
                        <span style={{ fontSize: "0.875rem", fontWeight: 700, color: "#1f2937" }}>
                            {progressPercent}%
                        </span>
                    </div>
                </div>
            </div>

            {/* Pipeline Stages */}
            <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(4, 1fr)",
                gap: "0.75rem",
                marginBottom: "1.5rem"
            }}>
                <PipelineStage
                    icon={<Package size={20} />}
                    title="Queued"
                    count={pendingCount * 5}
                    color="#6366f1"
                    isActive={currentPhase === "batching"}
                />
                <PipelineStage
                    icon={<Brain size={20} />}
                    title="Translating"
                    count={processingCount}
                    color="#3b82f6"
                    isActive={currentPhase === "translating"}
                    subtitle={`${processingCount} batches`}
                />
                <PipelineStage
                    icon={<Shield size={20} />}
                    title="Quality Gates"
                    count={translatedCount}
                    color="#10b981"
                    isActive={currentPhase === "quality"}
                />
                <PipelineStage
                    icon={<CheckCircle2 size={20} />}
                    title="Complete"
                    count={translatedCount}
                    color="#22c55e"
                    isActive={currentPhase === "complete"}
                />
            </div>

            {/* Batch Queue */}
            <div style={{
                background: "#f9fafb",
                borderRadius: "12px",
                padding: "1rem",
                border: "1px solid #e5e7eb"
            }}>
                <h3 style={{
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    color: "#6b7280",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    margin: "0 0 0.75rem"
                }}>
                    Batch Processing Queue
                </h3>

                <div style={{
                    display: "flex",
                    gap: "0.5rem",
                    overflowX: "auto",
                    paddingBottom: "0.5rem"
                }}>
                    {batches.slice(0, 12).map((batch) => (
                        <BatchCard key={batch.id} batch={batch} />
                    ))}

                    {batches.length > 12 && (
                        <div style={{
                            minWidth: "80px",
                            padding: "0.75rem",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            color: "#9ca3af",
                            fontSize: "0.75rem"
                        }}>
                            +{batches.length - 12} more
                        </div>
                    )}

                    {batches.length === 0 && (
                        <div style={{
                            color: "#9ca3af",
                            padding: "1rem",
                            textAlign: "center",
                            width: "100%",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: "0.5rem"
                        }}>
                            <Loader2 size={16} className="animate-spin" />
                            Creating batches...
                        </div>
                    )}
                </div>
            </div>

            {/* Activity Status */}
            <div style={{
                marginTop: "1rem",
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                fontSize: "0.8125rem",
                color: "#6b7280"
            }}>
                <span style={{
                    width: "8px",
                    height: "8px",
                    borderRadius: "50%",
                    background: currentPhase === "complete" ? "#22c55e" : "#3b82f6",
                    animation: currentPhase !== "complete" ? "pulse 2s infinite" : undefined
                }} />
                <span>
                    {currentPhase === "batching" && "Organizing segments into optimized batches..."}
                    {currentPhase === "translating" && `${processingCount} LLM agents translating concurrently...`}
                    {currentPhase === "quality" && "Running quality gates: terminology, glossary, unit checks..."}
                    {currentPhase === "complete" && "Translation complete! Ready for human review."}
                </span>
            </div>

            <style jsx global>{`
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.5; }
                }
                .animate-spin {
                    animation: spin 1s linear infinite;
                }
                @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    )
}

function PipelineStage({
    icon,
    title,
    count,
    color,
    isActive,
    subtitle
}: {
    icon: React.ReactNode
    title: string
    count: number
    color: string
    isActive: boolean
    subtitle?: string
}) {
    return (
        <div style={{
            background: isActive ? `${color}10` : "#f9fafb",
            border: `1px solid ${isActive ? color : "#e5e7eb"}`,
            borderRadius: "10px",
            padding: "1rem",
            textAlign: "center",
            transition: "all 0.2s ease"
        }}>
            <div style={{
                color: isActive ? color : "#9ca3af",
                marginBottom: "0.5rem",
                display: "flex",
                justifyContent: "center"
            }}>
                {icon}
            </div>

            <div style={{
                fontSize: "1.25rem",
                fontWeight: 700,
                color: isActive ? "#1f2937" : "#9ca3af"
            }}>
                {count}
            </div>

            <div style={{
                fontSize: "0.6875rem",
                color: "#6b7280",
                marginTop: "0.125rem"
            }}>
                {title}
            </div>

            {subtitle && (
                <div style={{
                    fontSize: "0.625rem",
                    color: color,
                    marginTop: "0.25rem",
                    fontWeight: 500
                }}>
                    {subtitle}
                </div>
            )}
        </div>
    )
}

function BatchCard({ batch }: { batch: Batch }) {
    const statusConfig = {
        pending: { bg: "#f9fafb", border: "#e5e7eb", color: "#9ca3af" },
        processing: { bg: "#eff6ff", border: "#3b82f6", color: "#3b82f6" },
        complete: { bg: "#f0fdf4", border: "#22c55e", color: "#22c55e" },
        failed: { bg: "#fef2f2", border: "#ef4444", color: "#ef4444" }
    }

    const config = statusConfig[batch.status]

    return (
        <div style={{
            background: config.bg,
            border: `1px solid ${config.border}`,
            borderRadius: "8px",
            padding: "0.625rem",
            minWidth: "70px",
            textAlign: "center"
        }}>
            <div style={{
                fontSize: "0.6875rem",
                color: config.color,
                fontWeight: 600,
                marginBottom: "0.25rem"
            }}>
                Batch {batch.id + 1}
            </div>

            <div style={{
                display: "flex",
                gap: "2px",
                justifyContent: "center",
                flexWrap: "wrap"
            }}>
                {Array.from({ length: batch.segmentCount }).map((_, i) => (
                    <div
                        key={i}
                        style={{
                            width: "6px",
                            height: "6px",
                            borderRadius: "1px",
                            background: config.color
                        }}
                    />
                ))}
            </div>

            {batch.status === "processing" && (
                <Loader2
                    size={10}
                    style={{
                        color: config.color,
                        marginTop: "0.25rem",
                        animation: "spin 1s linear infinite"
                    }}
                />
            )}
            {batch.status === "complete" && (
                <CheckCircle2
                    size={10}
                    style={{ color: config.color, marginTop: "0.25rem" }}
                />
            )}
        </div>
    )
}
