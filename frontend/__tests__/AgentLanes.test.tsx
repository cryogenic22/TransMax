import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import {
  AgentLanes,
  type AgentActivity,
} from "@/components/ui/AgentLanes"

const SAMPLE: AgentActivity[] = [
  { id: "1", agent: "translator", label: "Translate batch 1", startedAt: "2026-05-09T17:23:00Z", durationMs: 4800, status: "complete" },
  { id: "2", agent: "reviewer", label: "Quality gates", startedAt: "2026-05-09T17:23:05Z", durationMs: 1200, status: "in_progress" },
]

describe("<AgentLanes>", () => {
  it("renders all four agent lanes when empty for any specific agent", () => {
    render(<AgentLanes activities={SAMPLE} />)
    expect(screen.getByText("Translator")).toBeInTheDocument()
    expect(screen.getByText("Reviewer")).toBeInTheDocument()
    expect(screen.getByText("Fixer")).toBeInTheDocument()
    expect(screen.getByText("Auditor")).toBeInTheDocument()
  })

  it("places each activity on its own agent's lane", () => {
    const { container } = render(<AgentLanes activities={SAMPLE} />)
    const transLane = container.querySelector("[data-agent='translator']")
    const revLane = container.querySelector("[data-agent='reviewer']")
    expect(transLane?.textContent).toContain("Translate batch 1")
    expect(revLane?.textContent).toContain("Quality gates")
    // Reviewer activity must NOT appear in translator lane.
    expect(transLane?.textContent).not.toContain("Quality gates")
  })

  it("formats duration in human-friendly units", () => {
    render(<AgentLanes activities={SAMPLE} />)
    expect(screen.getByText(/4\.8s/)).toBeInTheDocument()
    expect(screen.getByText(/1\.2s/)).toBeInTheDocument()
  })

  it("renders an empty state when there are no activities", () => {
    render(<AgentLanes activities={[]} />)
    expect(screen.getByText(/no agent activity yet/i)).toBeInTheDocument()
  })

  it("uses the aria-labelled region for screen readers", () => {
    render(<AgentLanes activities={SAMPLE} />)
    expect(screen.getByRole("region", { name: /agent activity/i })).toBeInTheDocument()
  })

  it("placeholder dash on empty lanes", () => {
    render(<AgentLanes activities={[SAMPLE[0]]} />)
    // Reviewer / fixer / auditor have nothing — should each render a dash.
    const dashes = screen.getAllByText("—")
    expect(dashes.length).toBeGreaterThanOrEqual(3)
  })
})
