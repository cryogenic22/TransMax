import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { ProvenanceChip } from "@/components/ui/ProvenanceChip"

describe("<ProvenanceChip>", () => {
  it("renders the source label", () => {
    render(<ProvenanceChip source="Translator agent" />)
    expect(screen.getByText("Translator agent")).toBeInTheDocument()
  })

  it("renders an optional version qualifier", () => {
    render(<ProvenanceChip source="Translator" version="prompt v1.0.0" />)
    expect(screen.getByText(/prompt v1\.0\.0/)).toBeInTheDocument()
  })

  it("renders a truncated hash when one is provided", () => {
    render(
      <ProvenanceChip
        source="Translator"
        hash="a3f9e2bc81d44a99b3ce0a2f7d18c4e5"
      />
    )
    expect(screen.getByText(/a3f9e2bc/)).toBeInTheDocument()
    expect(screen.getByText(/…/)).toBeInTheDocument()
  })

  it("includes the full hash in the title attribute for copy/inspect", () => {
    const { container } = render(
      <ProvenanceChip
        source="Translator"
        hash="a3f9e2bc81d44a99b3ce0a2f7d18c4e5"
      />
    )
    const span = container.querySelector("span")
    expect(span?.getAttribute("title")).toContain("a3f9e2bc81d44a99b3ce0a2f7d18c4e5")
  })

  it("does not render the fingerprint icon when no hash is provided", () => {
    const { container } = render(<ProvenanceChip source="Translator" />)
    // Fingerprint is the only svg in the chip; its absence verifies the conditional.
    expect(container.querySelector("svg")).not.toBeInTheDocument()
  })
})
