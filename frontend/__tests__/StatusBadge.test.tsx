import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { StatusBadge } from "@/components/ui/StatusBadge"

describe("<StatusBadge>", () => {
  it("renders the status text verbatim", () => {
    render(<StatusBadge status="APPROVED" />)
    expect(screen.getByText("APPROVED")).toBeInTheDocument()
  })

  it("applies the green variant for APPROVED / COMPLETED", () => {
    const { container } = render(<StatusBadge status="APPROVED" />)
    const span = container.querySelector("span")
    expect(span?.className).toMatch(/bg-green-100/)
  })

  it("applies the red variant for REJECTED / BLOCKED", () => {
    const { container } = render(<StatusBadge status="REJECTED" />)
    const span = container.querySelector("span")
    expect(span?.className).toMatch(/bg-red-100/)
  })

  it("applies the amber variant for REVIEW_REQUIRED / PROCESSING", () => {
    const { container } = render(<StatusBadge status="PROCESSING" />)
    const span = container.querySelector("span")
    expect(span?.className).toMatch(/bg-amber-100/)
  })

  it("falls back to slate variant for unknown status (PENDING)", () => {
    const { container } = render(<StatusBadge status="PENDING" />)
    const span = container.querySelector("span")
    expect(span?.className).toMatch(/bg-slate-100/)
  })

  it("normalises lowercase status to uppercase for the variant lookup", () => {
    const { container } = render(<StatusBadge status="approved" />)
    const span = container.querySelector("span")
    // text rendered as-is, but the variant matches normalised
    expect(span).toHaveTextContent("approved")
    expect(span?.className).toMatch(/bg-green-100/)
  })

  it("merges additional className prop", () => {
    const { container } = render(
      <StatusBadge status="APPROVED" className="ml-2" data-testid="badge" />
    )
    const span = container.querySelector("[data-testid='badge']")
    expect(span?.className).toMatch(/ml-2/)
  })
})
