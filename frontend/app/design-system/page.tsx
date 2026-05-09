import { GlassCard } from "@/components/ui/GlassCard"
import { StatusBadge } from "@/components/ui/StatusBadge"

export default function DesignSystemPage() {
    return (
        <div className="min-h-screen bg-slate-50 p-10 font-sans text-slate-900">
            <header className="mb-10">
                <h1 className="text-3xl font-bold tracking-tight text-primary">TransMax Clinical Design System</h1>
                <p className="text-muted-foreground mt-2">Trust Experience Verification (Sprint 5.1)</p>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* SECTION 1: COLOR PALETTE */}
                <section className="space-y-4">
                    <h2 className="text-xl font-semibold border-b pb-2">1. Trust Palette</h2>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <div className="h-16 w-full bg-primary rounded shadow-sm"></div>
                            <p className="text-xs font-mono">Primary (Trust Blue)</p>
                        </div>
                        <div className="space-y-2">
                            <div className="h-16 w-full bg-medical-green rounded shadow-sm"></div>
                            <p className="text-xs font-mono">Medical Green</p>
                        </div>
                        <div className="space-y-2">
                            <div className="h-16 w-full bg-alert-red rounded shadow-sm"></div>
                            <p className="text-xs font-mono">Alert Red</p>
                        </div>
                        <div className="space-y-2">
                            <div className="h-16 w-full bg-background border rounded shadow-sm"></div>
                            <p className="text-xs font-mono">Background (Medical White)</p>
                        </div>
                    </div>
                </section>

                {/* SECTION 2: COMPONENTS */}
                <section className="space-y-4">
                    <h2 className="text-xl font-semibold border-b pb-2">2. Clinical Components</h2>

                    <div className="space-y-4">
                        <h3 className="text-sm font-medium text-muted-foreground">GlassCard (The "Glass Box")</h3>
                        <GlassCard>
                            <h4 className="font-semibold">Audit Record #8821</h4>
                            <p className="text-sm mt-1 text-slate-600">
                                Immutable record hash: <code className="font-mono bg-slate-100 px-1 rounded">0x7F...2A</code>
                            </p>
                        </GlassCard>
                    </div>

                    <div className="space-y-4">
                        <h3 className="text-sm font-medium text-muted-foreground">Status Badges</h3>
                        <div className="flex gap-2">
                            <StatusBadge status="APPROVED" />
                            <StatusBadge status="REVIEW_REQUIRED" />
                            <StatusBadge status="BLOCKED" />
                            <StatusBadge status="PENDING" />
                        </div>
                    </div>
                </section>

                {/* SECTION 3: TYPOGRAPHY */}
                <section className="col-span-1 md:col-span-2 space-y-4">
                    <h2 className="text-xl font-semibold border-b pb-2">3. Typography</h2>
                    <div className="space-y-2">
                        <h1 className="text-4xl font-extrabold tracking-tight">Heading 1 (Inter)</h1>
                        <h2 className="text-3xl font-semibold tracking-tight">Heading 2 (Inter)</h2>
                        <p className="leading-7">
                            This is standard body text explaining the clinical trial results.
                            It should be legible and calm.
                        </p>
                        <pre className="p-4 bg-slate-900 text-slate-50 rounded-lg font-mono text-sm">
                            {`// Data Code Block (JetBrains Mono)
{
  "drift_score": 0.0,
  "status": "PASS"
}`}
                        </pre>
                    </div>
                </section>
            </div>
        </div>
    )
}
