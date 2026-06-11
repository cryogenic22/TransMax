import { describe, it, expect } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { QualityDashboard } from "@/components/ui/QualityDashboard"

// TMX-UX-QDASH-REAL: the dashboard must render ONLY real engine data — never
// the old fabricated accuracy/fluency/terminology bars, and an honest
// "scoring unavailable" state when the scorer could not run (A3).

describe("<QualityDashboard>", () => {
  it("never renders fabricated dimension labels", () => {
    render(
      <QualityDashboard
        confidence={92}
        scoringAvailable={true}
        breakdown={{ base: 100, deterministic_penalty: 8 }}
        breakdownReasoning={["Defects: -8.0 (1 Major, 0 Minor)"]}
        sourceText="Some clinical text"
      />
    )
    // The old mock surfaced these as hard-coded dimension scores.
    expect(screen.queryByText("Accuracy")).not.toBeInTheDocument()
    expect(screen.queryByText("Fluency")).not.toBeInTheDocument()
    expect(screen.queryByText("Terminology")).not.toBeInTheDocument()
  })

  it("shows the real confidence and, when expanded, the real penalty + reasoning", () => {
    const { container } = render(
      <QualityDashboard
        confidence={92}
        scoringAvailable={true}
        breakdown={{ base: 100, deterministic_penalty: 8 }}
        breakdownReasoning={["Defects: -8.0 (1 Major, 0 Minor)"]}
        sourceText="plain text"
      />
    )
    expect(screen.getByText("92.0%")).toBeInTheDocument()
    // Expand the panel (header carries role="button").
    fireEvent.click(container.querySelector('[role="button"]')!)
    expect(screen.getByText("Score Breakdown")).toBeInTheDocument()
    expect(screen.getByText("QA Defects")).toBeInTheDocument()
    expect(screen.getByText("−8")).toBeInTheDocument()
    expect(
      screen.getByText("Defects: -8.0 (1 Major, 0 Minor)")
    ).toBeInTheDocument()
  })

  it("renders an honest 'scoring unavailable' state (no fabricated number)", () => {
    render(
      <QualityDashboard
        confidence={null}
        scoringAvailable={false}
        sourceText="text"
      />
    )
    expect(
      screen.getByText(/Quality scoring unavailable/i)
    ).toBeInTheDocument()
    // No confidence percentage is shown — it reads N/A, not a green 90%.
    expect(screen.getByText("N/A")).toBeInTheDocument()
    expect(screen.queryByText(/90\.0%/)).not.toBeInTheDocument()
  })
})
