"use client"

import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Brain, CheckCircle, Loader2, ShieldCheck, FileText, Scale } from "lucide-react"
import { cn } from "@/lib/utils"

export type AgentStep = {
    id: string
    label: string
    status: 'idle' | 'active' | 'done' | 'error'
    details?: string
}

interface LiveIslandProps {
    steps: AgentStep[]
    currentStepId: string | null
    className?: string
}

export function LiveIsland({ steps, currentStepId, className }: LiveIslandProps) {
    const activeIndex = steps.findIndex(s => s.id === currentStepId)
    const activeStep = steps[activeIndex]

    return (
        <div className={cn("fixed bottom-8 left-1/2 -translate-x-1/2 z-50", className)}>
            <motion.div
                layout
                initial={{ width: 300, height: 60, opacity: 0, y: 50 }}
                animate={{
                    width: activeStep?.details ? 450 : 320,
                    height: "auto",
                    opacity: 1,
                    y: 0
                }}
                className="bg-black/80 backdrop-blur-xl border border-white/10 rounded-full shadow-2xl overflow-hidden flex flex-col justify-center"
            >
                <div className="flex items-center p-4 gap-4">
                    {/* Icon Ring */}
                    <div className="relative w-10 h-10 flex-shrink-0 flex items-center justify-center">
                        <AnimatePresence mode="wait">
                            <motion.div
                                key={activeStep?.id || "idle"}
                                initial={{ scale: 0.5, opacity: 0 }}
                                animate={{ scale: 1, opacity: 1 }}
                                exit={{ scale: 0.5, opacity: 0 }}
                                className="absolute inset-0 flex items-center justify-center"
                            >
                                {getStepIcon(activeStep?.id)}
                            </motion.div>
                        </AnimatePresence>

                        {/* Spinner Ring */}
                        {activeStep && activeStep.status === 'active' && (
                            <motion.div
                                className="absolute inset-0 border-2 border-transparent border-t-primary rounded-full"
                                animate={{ rotate: 360 }}
                                transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                            />
                        )}
                    </div>

                    {/* Text Content */}
                    <div className="flex-1 min-w-0">
                        <AnimatePresence mode="wait">
                            <motion.div
                                key={activeStep?.id || "waiting"}
                                initial={{ y: 20, opacity: 0 }}
                                animate={{ y: 0, opacity: 1 }}
                                exit={{ y: -20, opacity: 0 }}
                                className="flex flex-col"
                            >
                                <span className="text-sm font-medium text-white truncate">
                                    {activeStep?.label || "Waiting for task..."}
                                </span>
                                {activeStep?.details && (
                                    <span className="text-xs text-white/50 truncate">
                                        {activeStep.details}
                                    </span>
                                )}
                            </motion.div>
                        </AnimatePresence>
                    </div>

                    {/* Progress Indicator */}
                    <div className="text-xs font-mono text-white/30">
                        {activeIndex > -1 ? activeIndex + 1 : 0}/{steps.length}
                    </div>
                </div>

                {/* Glass Box Detail Expansion (Optional) */}
                {/* This could show logs or JSON data in a future iteration */}
            </motion.div>
        </div>
    )
}

function getStepIcon(stepId?: string) {
    if (!stepId) return <Brain className="w-5 h-5 text-white/20" />

    switch (true) {
        case stepId.includes("ingest"): return <FileText className="w-5 h-5 text-blue-400" />
        case stepId.includes("pii"): return <ShieldCheck className="w-5 h-5 text-purple-400" />
        case stepId.includes("translate"): return <Brain className="w-5 h-5 text-emerald-400" />
        case stepId.includes("gate"): return <Scale className="w-5 h-5 text-orange-400" />
        case stepId.includes("done"): return <CheckCircle className="w-5 h-5 text-green-500" />
        default: return <Loader2 className="w-5 h-5 text-white" />
    }
}
