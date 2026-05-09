"use client"

import { useState, useEffect } from "react"
import { useRouter, useParams, useSearchParams } from "next/navigation"
import { motion } from "framer-motion"
import {
    CheckCircle,
    Circle,
    Loader2,
    Shield,
    FileSearch,
    Languages,
    ClipboardCheck,
    Sparkles,
    ArrowRight,
    Globe
} from "lucide-react"

interface PipelineStep {
    id: string
    label: string
    description: string
    icon: React.ReactNode
    status: 'pending' | 'active' | 'complete' | 'error'
}

const PIPELINE_STEPS: PipelineStep[] = [
    {
        id: 'validate',
        label: 'Validating Input',
        description: 'Checking document format and metadata...',
        icon: <FileSearch className="w-5 h-5" />,
        status: 'pending'
    },
    {
        id: 'segment',
        label: 'Extracting Segments',
        description: 'Parsing content into translatable units...',
        icon: <FileSearch className="w-5 h-5" />,
        status: 'pending'
    },
    {
        id: 'translate',
        label: 'AI Translation',
        description: 'Translating with GPT-4 + Glossary constraints...',
        icon: <Languages className="w-5 h-5" />,
        status: 'pending'
    },
    {
        id: 'gates',
        label: 'Quality Gates',
        description: 'Running pharma safety checks (units, negations, PII)...',
        icon: <Shield className="w-5 h-5" />,
        status: 'pending'
    },
    {
        id: 'refine',
        label: 'Auto-Refinement',
        description: 'Fixing detected issues via reflexion loop...',
        icon: <Sparkles className="w-5 h-5" />,
        status: 'pending'
    },
    {
        id: 'finalize',
        label: 'Finalizing',
        description: 'Generating quality scorecard and audit trail...',
        icon: <ClipboardCheck className="w-5 h-5" />,
        status: 'pending'
    },
]

export default function TranslatePage() {
    const router = useRouter()
    const params = useParams()
    const searchParams = useSearchParams()
    const jobId = params.jobId as string
    const targetLang = searchParams.get('target') || 'fr'

    const [steps, setSteps] = useState<PipelineStep[]>(PIPELINE_STEPS)
    const [currentIndex, setCurrentIndex] = useState(0)
    const [isComplete, setIsComplete] = useState(false)
    const [elapsedSeconds, setElapsedSeconds] = useState(0)
    const [logs, setLogs] = useState<string[]>([])

    // Simulate pipeline execution
    useEffect(() => {
        const timer = setInterval(() => {
            setElapsedSeconds(s => s + 1)
        }, 1000)

        const runPipeline = async () => {
            for (let i = 0; i < PIPELINE_STEPS.length; i++) {
                // Set current step to active
                setCurrentIndex(i)
                setSteps(prev => prev.map((s, idx) =>
                    idx === i ? { ...s, status: 'active' } : s
                ))
                setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] Starting: ${PIPELINE_STEPS[i].label}`])

                // Simulate processing time
                const duration = PIPELINE_STEPS[i].id === 'translate' ? 3000 :
                    PIPELINE_STEPS[i].id === 'gates' ? 2000 : 1200

                await new Promise(resolve => setTimeout(resolve, duration))

                // Mark complete
                setSteps(prev => prev.map((s, idx) =>
                    idx === i ? { ...s, status: 'complete' } : s
                ))
                setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] Completed: ${PIPELINE_STEPS[i].label}`])
            }

            setIsComplete(true)
            clearInterval(timer)
        }

        runPipeline()

        return () => clearInterval(timer)
    }, [])

    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60)
        const secs = seconds % 60
        return `${mins}:${secs.toString().padStart(2, '0')}`
    }

    const completedCount = steps.filter(s => s.status === 'complete').length

    return (
        <main className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>
            {/* Navigation */}
            <nav className="glass border-b" style={{ borderColor: 'var(--surface-border)' }}>
                <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg gradient-bg flex items-center justify-center">
                            <Globe className="w-4 h-4 text-white" />
                        </div>
                        <span className="font-semibold text-lg" style={{ color: 'var(--text-primary)' }}>
                            TransMax
                        </span>
                    </div>
                    <div className="flex items-center gap-4">
                        <span className="badge badge-info">
                            Job: {jobId}
                        </span>
                    </div>
                </div>
            </nav>

            <div className="max-w-4xl mx-auto px-6 py-12">
                {/* Header */}
                <div className="text-center mb-12">
                    <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
                        {isComplete ? 'Translation Complete' : 'Translation in Progress'}
                    </h1>
                    <p style={{ color: 'var(--text-secondary)' }}>
                        Target: {targetLang.toUpperCase()} • Elapsed: {formatTime(elapsedSeconds)}
                    </p>
                </div>

                {/* Progress Bar */}
                <div className="mb-8">
                    <div className="flex justify-between text-sm mb-2">
                        <span style={{ color: 'var(--text-secondary)' }}>Progress</span>
                        <span style={{ color: 'var(--text-primary)' }} className="font-medium">
                            {completedCount} / {steps.length} steps
                        </span>
                    </div>
                    <div className="h-2 rounded-full" style={{ background: 'var(--bg-tertiary)' }}>
                        <motion.div
                            className="h-full rounded-full gradient-bg"
                            initial={{ width: 0 }}
                            animate={{ width: `${(completedCount / steps.length) * 100}%` }}
                            transition={{ duration: 0.5 }}
                        />
                    </div>
                </div>

                {/* Pipeline Steps */}
                <div className="card-static mb-8">
                    <div className="space-y-1">
                        {steps.map((step, index) => (
                            <div
                                key={step.id}
                                className={`flex items-center gap-4 p-4 rounded-lg transition-all ${step.status === 'active' ? 'bg-blue-50' : ''
                                    }`}
                                style={{
                                    borderLeft: step.status === 'active' ? '3px solid var(--brand-500)' : '3px solid transparent'
                                }}
                            >
                                {/* Icon */}
                                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${step.status === 'complete' ? 'bg-green-100' :
                                    step.status === 'active' ? 'bg-blue-100' :
                                        'bg-gray-100'
                                    }`}>
                                    {step.status === 'complete' ? (
                                        <CheckCircle className="w-5 h-5" style={{ color: 'var(--success-600)' }} />
                                    ) : step.status === 'active' ? (
                                        <Loader2 className="w-5 h-5 animate-spin" style={{ color: 'var(--brand-500)' }} />
                                    ) : (
                                        <Circle className="w-5 h-5" style={{ color: 'var(--text-dim)' }} />
                                    )}
                                </div>

                                {/* Label */}
                                <div className="flex-1">
                                    <div className="font-medium" style={{
                                        color: step.status === 'active' ? 'var(--brand-600)' :
                                            step.status === 'complete' ? 'var(--text-primary)' :
                                                'var(--text-muted)'
                                    }}>
                                        {step.label}
                                    </div>
                                    <div className="text-sm" style={{ color: 'var(--text-muted)' }}>
                                        {step.description}
                                    </div>
                                </div>

                                {/* Status Badge */}
                                {step.status === 'complete' && (
                                    <span className="badge badge-success">Done</span>
                                )}
                                {step.status === 'active' && (
                                    <span className="badge badge-info">Running</span>
                                )}
                            </div>
                        ))}
                    </div>
                </div>

                {/* Live Log */}
                <div className="card-static mb-8">
                    <div className="flex items-center gap-2 mb-4">
                        <div className="w-2 h-2 rounded-full animate-pulse"
                            style={{ background: isComplete ? 'var(--success-500)' : 'var(--brand-500)' }} />
                        <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
                            Agent Log
                        </span>
                    </div>
                    <div className="bg-neutral-900 text-neutral-100 rounded-lg p-4 font-mono text-sm max-h-48 overflow-y-auto">
                        {logs.map((log, i) => (
                            <div key={i} className="py-0.5 opacity-80">{log}</div>
                        ))}
                        {!isComplete && (
                            <div className="py-0.5 flex items-center gap-2">
                                <span className="animate-pulse">▊</span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Complete CTA */}
                {isComplete && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="text-center"
                    >
                        <button
                            onClick={() => router.push(`/review/${jobId}?target=${targetLang}`)}
                            className="btn btn-primary btn-lg"
                        >
                            Review Translation
                            <ArrowRight className="w-5 h-5" />
                        </button>
                    </motion.div>
                )}
            </div>
        </main>
    )
}
