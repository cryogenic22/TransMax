"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { Check, Edit2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { DefectChip } from "./DefectChip"
import { ConfidenceMeter } from "@/components/ui/ConfidenceMeter"
import { ProvenanceChip } from "@/components/ui/ProvenanceChip"
import {
    StatusLifecycle,
    type LifecycleStatus,
} from "@/components/ui/StatusLifecycle"
import type { PharmaSegment, SegmentStatus } from "@/lib/mock_pharma_job"

// Map the segment-level status union (mock + real) onto the canonical
// LifecycleStatus the design-system pill renders. TMX-3603-reviewer.
const STATUS_TO_LIFECYCLE: Record<SegmentStatus, LifecycleStatus> = {
    pending: "pending",
    review_required: "reviewed",
    approved: "approved",
    rejected: "blocked",
}

interface ReviewSegmentProps {
    segment: PharmaSegment;
    onStatusChange: (id: string, newStatus: PharmaSegment['status']) => void;
    onUpdateText: (id: string, newText: string) => void;
}

export function ReviewSegment({ segment, onStatusChange, onUpdateText }: ReviewSegmentProps) {
    const [isEditing, setIsEditing] = useState(false)
    const [draftText, setDraftText] = useState(segment.target_text)

    const isFlagged = segment.status === 'review_required'
    const isApproved = segment.status === 'approved'

    const handleSave = () => {
        onUpdateText(segment.id, draftText)
        onStatusChange(segment.id, 'approved')
        setIsEditing(false)
    }

    // Score 0-1 → 0-100 for the ConfidenceMeter scale.
    const confidencePct = Math.round((segment.confidence_score ?? 0) * 100)
    const lifecycleStatus = STATUS_TO_LIFECYCLE[segment.status]
    // Latest agent in the reasoning trace becomes the provenance label.
    const lastAgent = segment.reasoning_trace?.[segment.reasoning_trace.length - 1]

    return (
        <motion.div
            layout
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`
                group grid grid-cols-12 gap-0 border-b border-slate-100 last:border-0
                hover:bg-slate-50 transition-colors
                ${isFlagged ? 'bg-amber-50/30 hover:bg-amber-50/50' : ''}
                ${isApproved ? 'bg-green-50/10' : ''}
            `}
        >
            {/* ID / Status Column — TMX-3603-reviewer adds StatusLifecycle
                + ConfidenceMeter so a reviewer scans status + trust at a
                glance, not by reading status copy. */}
            <div className="col-span-1 p-4 border-r border-slate-100 flex flex-col items-center justify-start gap-2 text-xs text-slate-400 font-mono pt-6">
                <span>{segment.index}</span>
                <StatusLifecycle status={lifecycleStatus} />
                <ConfidenceMeter score={confidencePct} />
                {isFlagged && <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />}
            </div>

            {/* Source Text */}
            <div className="col-span-5 p-4 py-6 border-r border-slate-100 text-slate-700 font-sans leading-relaxed">
                {segment.source_text}
            </div>

            {/* Target Text (Editable) */}
            <div className="col-span-6 p-4 py-6 relative group/target">
                {/* Defects Overlay */}
                {segment.defects.length > 0 && !isEditing && (
                    <div className="flex flex-wrap gap-2 mb-3">
                        {segment.defects.map(d => (
                            <DefectChip key={d.id} type={d.type} severity={d.severity} message={d.message} />
                        ))}
                    </div>
                )}

                {isEditing ? (
                    <div className="space-y-3">
                        <textarea
                            value={draftText}
                            onChange={(e) => setDraftText(e.target.value)}
                            className="w-full p-3 rounded-md border border-blue-200 bg-white shadow-sm focus:ring-2 focus:ring-blue-500 focus:outline-none min-h-[100px] font-sans"
                            autoFocus
                        />
                        <div className="flex gap-2 justify-end">
                            <Button size="sm" variant="ghost" onClick={() => setIsEditing(false)}>Cancel</Button>
                            <Button size="sm" onClick={handleSave} className="bg-blue-600 hover:bg-blue-700 text-white">
                                <Check className="w-4 h-4 mr-1" /> Save & Approve
                            </Button>
                        </div>
                    </div>
                ) : (
                    <div className="relative">
                        <p className={`
                            font-sans leading-relaxed
                            ${isFlagged ? 'text-amber-900' : 'text-slate-800'}
                        `}>
                            {segment.target_text}
                        </p>

                        {/* Provenance — A1 audit-by-default made visible per
                            row. Surfaces the producing step + when. */}
                        {lastAgent ? (
                            <div className="mt-3">
                                <ProvenanceChip
                                    source={lastAgent.step}
                                    timestamp={lastAgent.timestamp}
                                />
                            </div>
                        ) : null}

                        {/* Hover Actions */}
                        <div className="absolute top-0 right-0 opacity-0 group-hover/target:opacity-100 transition-opacity flex gap-2 bg-white/80 backdrop-blur px-2 py-1 rounded shadow-sm border border-slate-100 -mt-8">
                            <button onClick={() => setIsEditing(true)} className="p-1 hover:text-blue-600" title="Edit">
                                <Edit2 className="w-4 h-4" />
                            </button>
                            {isFlagged && (
                                <button onClick={() => onStatusChange(segment.id, 'approved')} className="p-1 hover:text-green-600" title="Quick Approve">
                                    <Check className="w-4 h-4" />
                                </button>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </motion.div>
    )
}
