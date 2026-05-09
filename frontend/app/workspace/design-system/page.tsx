"use client"

import { AIMoment } from "@/components/ui/AIMoment"
import { ProvenanceChip } from "@/components/ui/ProvenanceChip"
import {
  StatusLifecycle,
  type LifecycleStatus,
} from "@/components/ui/StatusLifecycle"

const ALL_STATES: LifecycleStatus[] = [
  "pending",
  "translating",
  "translated",
  "reviewed",
  "approved",
  "blocked",
]

export default function WorkspaceDesignSystemPage() {
  return (
    <main className="mx-auto max-w-3xl space-y-12 px-6 py-10">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">
          TransMax Design System
        </h1>
        <p className="text-muted-foreground text-sm leading-relaxed">
          The three patterns codified by TMX-3602 (rescape designer review,
          May 2026). Drop these into any surface to keep the visual contract
          consistent across the platform. Tokens come from TMX-3601.
        </p>
      </header>

      {/* AI Moment — wraps any AI-generated artefact. */}
      <section className="space-y-3" aria-labelledby="ai-moment-heading">
        <h2 id="ai-moment-heading" className="text-lg font-semibold">
          AI Moment
        </h2>
        <p className="text-sm text-muted-foreground">
          Wraps every AI-generated artefact in the platform&apos;s signature
          violet → cyan gradient. Carries model identity, prompt version, and
          (optionally) cost telemetry — A6 says LLMs are qualified suppliers,
          and the chip is what makes that visible.
        </p>

        <AIMoment
          model="Claude Sonnet 4.6"
          promptVersion="translator-v1.0.0"
          tokensIn={142}
          tokensOut={89}
          generatedAt="2026-05-09T17:23:45Z"
          explanation="Two-pass translate then a deterministic quality-gate sweep. The gate fired no critical defects; this output passed."
        >
          <p className="text-sm leading-relaxed">
            Tomar 500 mg dos veces al día con las comidas. No exceder los
            1000 mg en 24 horas.
          </p>
        </AIMoment>

        <AIMoment model="GPT-4o" promptVersion="fixer-v1.0.0">
          <p className="text-sm leading-relaxed">
            Substituted &ldquo;every 6 hours&rdquo; → &ldquo;cada 6 horas&rdquo;
            after the frequency-pattern gate fired (FREQ_MISMATCH).
          </p>
        </AIMoment>
      </section>

      {/* Provenance Chip — small chip near any content block. */}
      <section className="space-y-3" aria-labelledby="provenance-heading">
        <h2 id="provenance-heading" className="text-lg font-semibold">
          Provenance Chip
        </h2>
        <p className="text-sm text-muted-foreground">
          A small chip beside any content block. Surfaces source, version,
          timestamp, and the audit-chain hash. Hover the chip to see the
          full hash for copy/inspect. Audit-by-default (A1) made visible.
        </p>

        <div className="flex flex-wrap gap-2">
          <ProvenanceChip source="Translator agent" />
          <ProvenanceChip source="Reviewer agent" version="prompt v1.0.0" />
          <ProvenanceChip
            source="Fixer agent"
            version="prompt v1.0.0"
            timestamp="2026-05-09T17:25Z"
          />
          <ProvenanceChip
            source="Auditor agent"
            version="rev 4"
            timestamp="2026-05-09T17:25Z"
            hash="a3f9e2bc81d44a99b3ce0a2f7d18c4e5"
          />
          <ProvenanceChip source="TM exact match" version="tm-2024-q4" />
          <ProvenanceChip source="Glossary lookup" version="EDQM v2024-01" />
        </div>
      </section>

      {/* Status Lifecycle — 6-state pill with iconography. */}
      <section className="space-y-3" aria-labelledby="lifecycle-heading">
        <h2 id="lifecycle-heading" className="text-lg font-semibold">
          Status Lifecycle
        </h2>
        <p className="text-sm text-muted-foreground">
          Six canonical states a segment or job moves through. One pill, one
          prop. Adding a state means: extend the union, extend the map, add
          the matching CSS variables. Used everywhere status appears so a
          reviewer scans by colour + icon, not by reading text.
        </p>

        <div className="flex flex-wrap gap-2">
          {ALL_STATES.map(s => (
            <StatusLifecycle key={s} status={s} />
          ))}
        </div>

        <p className="text-xs text-muted-foreground pt-2">
          Optional label override (e.g. for a job that needs a custom status
          string while keeping the colour family):
        </p>
        <div className="flex flex-wrap gap-2">
          <StatusLifecycle status="reviewed" label="Awaiting QC" />
          <StatusLifecycle status="blocked" label="Critical defect" />
          <StatusLifecycle status="translating" label="LLM in flight" />
        </div>
      </section>

      {/* Composition — show the three patterns together as they would be
          used on a real segment row. */}
      <section className="space-y-3" aria-labelledby="composition-heading">
        <h2 id="composition-heading" className="text-lg font-semibold">
          Composition
        </h2>
        <p className="text-sm text-muted-foreground">
          The three patterns composed as they would appear on a single
          segment row in the reviewer surface.
        </p>

        <div className="rounded-lg border bg-card p-4 space-y-3">
          <div className="flex items-center gap-2">
            <StatusLifecycle status="translated" />
            <ProvenanceChip
              source="Translator agent · gpt-4o"
              version="translator-v1.0.0"
              timestamp="2026-05-09T17:23Z"
              hash="a3f9e2bc81d44a99b3ce0a2f7d18c4e5"
            />
          </div>

          <p className="text-sm">
            <span className="text-muted-foreground">EN:</span> Take 500 mg
            twice daily with meals. Do not exceed 1000 mg in 24 hours.
          </p>

          <AIMoment
            model="Claude Sonnet 4.6"
            promptVersion="translator-v1.0.0"
            tokensIn={142}
            tokensOut={89}
            generatedAt="2026-05-09T17:23:45Z"
            explanation="Tier-2 cascade: TM miss → glossary partial → LLM. All deterministic gates green."
          >
            <p className="text-sm leading-relaxed">
              <span className="text-muted-foreground">ES:</span> Tomar 500 mg
              dos veces al día con las comidas. No exceder los 1000 mg en
              24 horas.
            </p>
          </AIMoment>
        </div>
      </section>
    </main>
  )
}
