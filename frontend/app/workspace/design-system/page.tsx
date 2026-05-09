"use client"

import { AIMoment } from "@/components/ui/AIMoment"
import { ProvenanceChip } from "@/components/ui/ProvenanceChip"
import {
  StatusLifecycle,
  type LifecycleStatus,
} from "@/components/ui/StatusLifecycle"
import {
  AgentLanes,
  type AgentActivity,
} from "@/components/ui/AgentLanes"
import {
  ActivityFeed,
  type ActivityEvent,
} from "@/components/ui/ActivityFeed"
import { DefectTrace } from "@/components/ui/DefectTrace"
import { RevisionIndicator } from "@/components/ui/RevisionIndicator"
import type { SegmentRevisions } from "@/lib/api"

// TMX-3702-demo: fixtures for the RevisionIndicator showcase.
const REVISION_FIXTURES: Array<{ caption: string; revisions: SegmentRevisions }> = [
  {
    caption: "Single-author insertion (the most common pharma case — author tweaks dosing).",
    revisions: {
      has_insertions: true,
      has_deletions: false,
      has_moves: false,
      authors: ["Dr. Reviewer"],
      dates: ["2026-04-01T10:00:00Z"],
    },
  },
  {
    caption: "Multi-author with both insertions and deletions; latest date wins for the headline.",
    revisions: {
      has_insertions: true,
      has_deletions: true,
      has_moves: false,
      authors: ["Auditor", "QC Lead"],
      dates: ["2026-04-02T11:00:00Z", "2026-04-08T16:30:00Z"],
    },
  },
  {
    caption: "Move-only (w:moveFrom / w:moveTo) with anonymous authoring — indicator still shows.",
    revisions: {
      has_insertions: false,
      has_deletions: false,
      has_moves: true,
      authors: [],
      dates: ["2026-04-05T09:00:00Z"],
    },
  },
  {
    caption: "TMX-3704-ui: moveFrom-only — text was relocated AWAY from this segment.",
    revisions: {
      has_insertions: false,
      has_deletions: false,
      has_moves: true,
      has_moves_from: true,
      has_moves_to: false,
      authors: ["Mover"],
      dates: ["2026-04-06T09:00:00Z"],
    },
  },
  {
    caption: "TMX-3704-ui: moveTo-only — text arrived HERE from elsewhere in the doc.",
    revisions: {
      has_insertions: false,
      has_deletions: false,
      has_moves: true,
      has_moves_from: false,
      has_moves_to: true,
      authors: ["Mover"],
      dates: ["2026-04-06T09:00:00Z"],
    },
  },
]

const ALL_STATES: LifecycleStatus[] = [
  "pending",
  "translating",
  "translated",
  "reviewed",
  "approved",
  "blocked",
]

// Fixture data — TMX-3603-wire replaces with live OTel + audit feed.
const DEMO_ACTIVITIES: AgentActivity[] = [
  { id: "a1", agent: "translator", label: "Translate batch 1", startedAt: "2026-05-09T17:23:00Z", durationMs: 4800,  status: "complete"    },
  { id: "a2", agent: "translator", label: "Translate batch 2", startedAt: "2026-05-09T17:23:05Z", durationMs: 5100,  status: "complete"    },
  { id: "a3", agent: "reviewer",   label: "Quality gates",     startedAt: "2026-05-09T17:23:10Z", durationMs: 1200,  status: "in_progress" },
  { id: "a4", agent: "fixer",      label: "Awaiting trigger",  startedAt: "2026-05-09T17:23:11Z",                    status: "in_progress" },
  { id: "a5", agent: "auditor",    label: "Chain seal",        startedAt: "2026-05-09T17:23:12Z", durationMs: 320,   status: "complete"    },
]

const DEMO_FEED: ActivityEvent[] = [
  {
    id: "f1",
    actor: { type: "user", id: "carol", name: "Carol (QC Reviewer)" },
    action: "approved",
    target: "Cardivex SmPC v2.1 — EN→DE",
    occurredAt: "2026-05-09T17:00:00Z",
  },
  {
    id: "f2",
    actor: { type: "agent", id: "translator", name: "Translator agent" },
    action: "translated",
    target: "segment 47 of Mounjaro PIL — EN→ES",
    occurredAt: "2026-05-09T17:55:30Z",
  },
  {
    id: "f3",
    actor: { type: "agent", id: "reviewer", name: "Reviewer agent" },
    action: "flagged FREQUENCY_MISMATCH on",
    target: "Atorlip PIL §4.4 EN→FR",
    occurredAt: "2026-05-09T17:42:00Z",
  },
  {
    id: "f4",
    actor: { type: "system", id: "drift-detector", name: "Drift detector" },
    action: "noted upstream change in",
    target: "EDQM glossary term “adverse event”",
    occurredAt: "2026-05-08T17:00:00Z",
  },
  {
    id: "f5",
    actor: { type: "agent", id: "auditor", name: "Auditor agent" },
    action: "sealed",
    target: "Cardivex SmPC v2.1 audit chain (anchor a3f9e2bc…)",
    occurredAt: "2026-05-09T17:00:30Z",
  },
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

      {/* AgentLanes — multi-agent swim-lane (TMX-3603). */}
      <section className="space-y-3" aria-labelledby="agentlanes-heading">
        <h2 id="agentlanes-heading" className="text-lg font-semibold">
          Agent Lanes
        </h2>
        <p className="text-sm text-muted-foreground">
          Live multi-agent execution view. One lane per agent (translator,
          reviewer, fixer, auditor) coloured by the agent identity tokens
          from TMX-3601. Activities are chips with start time, duration, and
          status. Used at the top of any in-flight job page so a reviewer
          immediately sees four entities at work — the platform&apos;s
          agentic posture made visible.
        </p>
        <AgentLanes activities={DEMO_ACTIVITIES} />
        <p className="text-xs text-muted-foreground">Empty state:</p>
        <AgentLanes activities={[]} />
      </section>

      {/* ActivityFeed — chronological audit-style stream (TMX-3603). */}
      <section className="space-y-3" aria-labelledby="feed-heading">
        <h2 id="feed-heading" className="text-lg font-semibold">
          Activity Feed
        </h2>
        <p className="text-sm text-muted-foreground">
          Chronological event stream — replaces zero-stat-cards on the
          dashboard (rescape Direction 2). For an auditable platform the
          right hero is the audit log, not &ldquo;Pending: 0 / Active: 0
          / Approved: 0&rdquo;. Avatars colour-code by actor type:
          violet=agent, blue=user, emerald=system.
        </p>
        <ActivityFeed items={DEMO_FEED} />
      </section>

      {/* DefectTrace — rich expandable defect card (TMX-3603-reasoning). */}
      <section className="space-y-3" aria-labelledby="defect-trace-heading">
        <h2 id="defect-trace-heading" className="text-lg font-semibold">
          Defect Trace
        </h2>
        <p className="text-sm text-muted-foreground">
          The rich, expandable counterpart to the compact{" "}
          <code>DefectChip</code>. Surfaces the <em>why</em> behind a
          defect: which deterministic gate fired, what rule matched, the
          suggested fix, and the multi-agent reasoning trace. A2 (quality
          at gates) made legible to a reviewer.
        </p>

        <DefectTrace
          defect={{
            id: "demo-1",
            type: "frequency_mismatch",
            severity: "critical",
            message:
              "Source says 'twice daily' but target rendered as 'once daily'.",
            suggestion: "Replace 'una vez al día' with 'dos veces al día'.",
            gate: "FrequencyGate",
            rule: "FREQ_BID_ES",
          }}
          reasoning={[
            { step: "Translator agent", status: "pass", details: "Initial pass via Claude Sonnet 4.6.", timestamp: "2026-05-09T17:23Z" },
            { step: "Frequency gate",   status: "fail", details: "Expected 'dos veces al día' or equivalent BID frequency; target uses UID form.", timestamp: "2026-05-09T17:24Z" },
            { step: "Fixer agent",      status: "warn", details: "Suggested correction; awaiting reviewer approval.", timestamp: "2026-05-09T17:25Z" },
          ]}
          defaultOpen
        />

        <DefectTrace
          defect={{
            id: "demo-2",
            type: "term_drift",
            severity: "major",
            message:
              "EDQM term 'serious adverse event' rendered as 'serious side-effect'.",
            suggestion: "Use the EDQM Standard Term: 'reacción adversa grave'.",
            gate: "GlossaryGate",
            rule: "EDQM_SAE_ES",
          }}
        />
      </section>

      {/* RevisionIndicator — DOCX tracked-changes pill (TMX-3702-v1). */}
      <section className="space-y-3" aria-labelledby="revision-indicator-heading">
        <h2 id="revision-indicator-heading" className="text-lg font-semibold">
          Revision Indicator
        </h2>
        <p className="text-sm text-muted-foreground">
          Surfaces DOCX tracked-change provenance on segment rows whose source
          carried <code>&lt;w:ins&gt;</code> / <code>&lt;w:del&gt;</code> /{" "}
          <code>&lt;w:moveFrom&gt;</code> / <code>&lt;w:moveTo&gt;</code>{" "}
          marks. Captured at ingestion (TMX-3700) and persisted in{" "}
          <code>Segment.element_meta.revisions</code>. Hover the pill for the
          full author + date list. A1 audit-by-default, made visible to the
          reviewer.
        </p>
        <ul className="space-y-3">
          {REVISION_FIXTURES.map(({ caption, revisions }, idx) => (
            <li
              key={idx}
              className="rounded-lg border bg-card p-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"
            >
              <p className="text-xs text-muted-foreground sm:max-w-md">{caption}</p>
              <RevisionIndicator revisions={revisions} />
            </li>
          ))}
        </ul>
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
