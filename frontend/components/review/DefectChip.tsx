
import { AlertCircle, FileWarning, Info } from "lucide-react"

export type Severity = 'critical' | 'major' | 'minor' | 'info';

interface DefectChipProps {
    type: string;
    severity: Severity;
    message?: string;
}

export function DefectChip({ type, severity, message }: DefectChipProps) {
    const styles = {
        critical: "bg-red-100 text-red-800 border-red-200",
        major: "bg-amber-100 text-amber-800 border-amber-200",
        minor: "bg-blue-50 text-blue-700 border-blue-200",
        info: "bg-slate-100 text-slate-600 border-slate-200"
    }

    const icons = {
        critical: <AlertCircle className="w-3 h-3" />,
        major: <FileWarning className="w-3 h-3" />,
        minor: <Info className="w-3 h-3" />,
        info: <Info className="w-3 h-3" />
    }

    return (
        <div className={`
            inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border
            ${styles[severity] || styles.info}
            cursor-help transition-all hover:ring-1 hover:ring-offset-1 ring-current
        `} title={message}>
            {icons[severity] || icons.info}
            <span className="capitalize">{type.replace('_', ' ')}</span>
        </div>
    )
}
