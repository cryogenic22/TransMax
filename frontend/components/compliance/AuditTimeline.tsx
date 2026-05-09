import * as React from "react"
import { CheckCircle, ShieldCheck, Lock } from "lucide-react"
import { GlassCard } from "@/components/ui/GlassCard"
import { cn } from "@/lib/utils"

interface AuditEntry {
    sequence_index: number
    event_type: string
    timestamp: string
    entry_hash: string
    payload_summary: { count: number }
}

interface AuditTimelineProps {
    entries: AuditEntry[]
    chainHeadHash: string
}

export function AuditTimeline({ entries, chainHeadHash }: AuditTimelineProps) {
    if (!entries || entries.length === 0) return null

    return (
        <div className="space-y-6">
            <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-medical-green" />
                Immutable Audit Chain
            </h3>

            <div className="relative border-l-2 border-slate-200 ml-3 space-y-8 pl-8 py-2">
                {entries.map((entry) => {
                    const isFailure = entry.event_type.includes("FAIL") || entry.event_type.includes("BLOCK");
                    const isCritical = entry.event_type.includes("GATE") || entry.event_type.includes("DECISION");

                    return (
                        <div key={entry.sequence_index} className="relative group">
                            {/* Dot */}
                            <div className={cn(
                                "absolute -left-[41px] top-1 w-5 h-5 rounded-full border-4 border-white shadow-sm z-10",
                                isFailure ? "bg-red-500" : isCritical ? "bg-primary" : "bg-slate-300"
                            )} />

                            <GlassCard className="p-4 relative hover:shadow-md transition-shadow">
                                <div className="flex justify-between items-start mb-2">
                                    <div>
                                        <div className={cn(
                                            "text-sm font-bold uppercase tracking-wider",
                                            isFailure ? "text-red-600" : "text-primary"
                                        )}>
                                            {entry.event_type.replace(/_/g, " ")}
                                        </div>
                                        <div className="text-xs text-slate-400 font-mono">
                                            {new Date(entry.timestamp).toLocaleString()}
                                        </div>
                                    </div>
                                    <div className="text-xs font-mono text-slate-300 bg-slate-900 px-2 py-1 rounded">
                                        Idx: {entry.sequence_index}
                                    </div>
                                </div>

                                {/* Hash Visualization */}
                                <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800">
                                    <div className="flex items-center gap-2 text-[10px] text-slate-400 font-mono">
                                        <Lock className="w-3 h-3" />
                                        <span className="truncate w-full block" title={entry.entry_hash}>
                                            HASH: {entry.entry_hash}
                                        </span>
                                    </div>
                                </div>
                            </GlassCard>
                        </div>
                    )
                })}
            </div>

            {/* Chain Head */}
            <div className="ml-3 pl-8">
                <div className="bg-slate-900 text-slate-300 p-4 rounded-lg font-mono text-xs break-all border border-slate-700">
                    <div className="text-slate-500 mb-1 uppercase text-[10px] font-bold">Verified Chain Head</div>
                    <div className="text-medical-green flex items-center gap-2">
                        <CheckCircle className="w-3 h-3" />
                        {chainHeadHash}
                    </div>
                </div>
            </div>
        </div>
    )
}
