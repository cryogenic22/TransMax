import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { JobStatusBadge } from "@/components/ui/JobStatusBadge"

// TMX-UX-STATUS-DRY: single source of truth for job-status badges, replacing
// two duplicated getStatusBadge helpers (one hard-coded hex colours).

describe("<JobStatusBadge>", () => {
  it("capitalises the status label", () => {
    render(<JobStatusBadge status="completed" />)
    expect(screen.getByText("Completed")).toBeInTheDocument()
  })

  it("uses the green variant for completed", () => {
    const { container } = render(<JobStatusBadge status="completed" />)
    expect(container.querySelector("span")?.className).toMatch(/bg-green-100/)
  })

  it("uses the blue variant for processing", () => {
    const { container } = render(<JobStatusBadge status="processing" />)
    expect(container.querySelector("span")?.className).toMatch(/bg-blue-100/)
  })

  it("uses the red variant for failed", () => {
    const { container } = render(<JobStatusBadge status="failed" />)
    expect(container.querySelector("span")?.className).toMatch(/bg-red-100/)
  })

  it("falls back to the queued (slate) variant for an unknown status", () => {
    const { container } = render(<JobStatusBadge status="weird" />)
    expect(container.querySelector("span")?.className).toMatch(/bg-slate-100/)
  })

  it("uses no hard-coded hex colours (regression on the old helper)", () => {
    const { container } = render(<JobStatusBadge status="completed" />)
    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{6}/)
  })
})
