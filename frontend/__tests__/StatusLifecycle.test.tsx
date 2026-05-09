import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { StatusLifecycle } from "@/components/ui/StatusLifecycle"

describe("<StatusLifecycle>", () => {
  it("renders every canonical state with its label", () => {
    const states = [
      "pending",
      "translating",
      "translated",
      "reviewed",
      "approved",
      "blocked",
    ] as const
    const labels: Record<typeof states[number], string> = {
      pending: "Pending",
      translating: "Translating",
      translated: "Translated",
      reviewed: "Reviewed",
      approved: "Approved",
      blocked: "Blocked",
    }
    for (const s of states) {
      const { unmount } = render(<StatusLifecycle status={s} />)
      expect(screen.getByText(labels[s])).toBeInTheDocument()
      unmount()
    }
  })

  it("applies the right token class for the approved state", () => {
    const { container } = render(<StatusLifecycle status="approved" />)
    const span = container.querySelector("span[role='status']")
    expect(span?.className).toMatch(/bg-status-approved-bg/)
    expect(span?.className).toMatch(/text-status-approved-fg/)
  })

  it("applies the spin animation only on the translating state", () => {
    const { container: a } = render(<StatusLifecycle status="translating" />)
    expect(a.querySelector("svg")?.getAttribute("class")).toMatch(/animate-spin/)
    const { container: b } = render(<StatusLifecycle status="approved" />)
    expect(b.querySelector("svg")?.getAttribute("class") ?? "").not.toMatch(/animate-spin/)
  })

  it("supports a label override while keeping the canonical aria-label", () => {
    render(<StatusLifecycle status="reviewed" label="Awaiting QC" />)
    expect(screen.getByText("Awaiting QC")).toBeInTheDocument()
    expect(
      screen.getByRole("status", { name: /Awaiting QC/i })
    ).toBeInTheDocument()
  })
})
