import { describe, it, expect } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import {
  DefectTrace,
  type DefectTraceData,
  type ReasoningStep,
} from "@/components/ui/DefectTrace"

const SAMPLE_DEFECT: DefectTraceData = {
  id: "d1",
  type: "frequency_mismatch",
  severity: "critical",
  message: "Source says 'twice daily' but target rendered 'once daily'.",
  suggestion: "Replace 'una vez al día' with 'dos veces al día'.",
  gate: "FrequencyGate",
  rule: "FREQ_BID_ES",
}

const SAMPLE_REASONING: ReasoningStep[] = [
  { step: "Translator agent", status: "pass", details: "Initial pass", timestamp: "2026-05-09T17:23Z" },
  { step: "Frequency gate",   status: "fail", details: "BID expected, UID found", timestamp: "2026-05-09T17:24Z" },
  { step: "Fixer agent",      status: "warn", details: "Suggested correction", timestamp: "2026-05-09T17:25Z" },
]

describe("<DefectTrace>", () => {
  it("renders the defect type humanised + message", () => {
    render(<DefectTrace defect={SAMPLE_DEFECT} />)
    expect(screen.getByText(/frequency mismatch/i)).toBeInTheDocument()
    expect(screen.getByText(/twice daily/)).toBeInTheDocument()
  })

  it("shows the gate and rule when provided", () => {
    render(<DefectTrace defect={SAMPLE_DEFECT} />)
    expect(screen.getByText("FrequencyGate")).toBeInTheDocument()
    expect(screen.getByText("FREQ_BID_ES")).toBeInTheDocument()
  })

  it("renders the suggestion if present", () => {
    render(<DefectTrace defect={SAMPLE_DEFECT} />)
    expect(screen.getByText(/Suggested:/)).toBeInTheDocument()
    expect(screen.getByText(/dos veces al día/)).toBeInTheDocument()
  })

  it("hides the reasoning trace by default and reveals on click", () => {
    render(<DefectTrace defect={SAMPLE_DEFECT} reasoning={SAMPLE_REASONING} />)
    expect(screen.queryByText(/BID expected/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /show reasoning trace/i }))
    expect(screen.getByText(/BID expected/)).toBeInTheDocument()
  })

  it("renders expanded when defaultOpen is true", () => {
    render(<DefectTrace defect={SAMPLE_DEFECT} reasoning={SAMPLE_REASONING} defaultOpen />)
    expect(screen.getByText(/BID expected/)).toBeInTheDocument()
  })

  it("does not render the reasoning toggle when there is no reasoning", () => {
    render(<DefectTrace defect={SAMPLE_DEFECT} />)
    expect(
      screen.queryByRole("button", { name: /reasoning trace/i })
    ).not.toBeInTheDocument()
  })

  it("applies the critical-severity styling", () => {
    const { container } = render(<DefectTrace defect={SAMPLE_DEFECT} />)
    const wrap = container.querySelector("div[role='region']")
    expect(wrap?.className).toMatch(/bg-red-50/)
  })

  it("applies the minor severity styling", () => {
    const { container } = render(
      <DefectTrace defect={{ ...SAMPLE_DEFECT, severity: "minor" }} />
    )
    const wrap = container.querySelector("div[role='region']")
    expect(wrap?.className).toMatch(/bg-blue-50/)
  })

  it("uses an aria-labelled region for screen readers", () => {
    render(<DefectTrace defect={SAMPLE_DEFECT} />)
    expect(
      screen.getByRole("region", { name: /defect: frequency_mismatch/i })
    ).toBeInTheDocument()
  })
})
