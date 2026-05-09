import { describe, it, expect } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { AIMoment } from "@/components/ui/AIMoment"

describe("<AIMoment>", () => {
  it("renders the model identifier in the header", () => {
    render(
      <AIMoment model="Claude Sonnet 4.6">
        <p>Translation output</p>
      </AIMoment>
    )
    expect(screen.getByText(/AI · Claude Sonnet 4.6/)).toBeInTheDocument()
    expect(screen.getByText("Translation output")).toBeInTheDocument()
  })

  it("renders the prompt version when provided", () => {
    render(
      <AIMoment model="GPT-4o" promptVersion="translator-v1.0.0">
        <p>x</p>
      </AIMoment>
    )
    expect(screen.getByText(/translator-v1.0.0/)).toBeInTheDocument()
  })

  it("renders token usage when both directions are provided", () => {
    render(
      <AIMoment model="GPT-4o" tokensIn={142} tokensOut={89}>
        <p>x</p>
      </AIMoment>
    )
    expect(screen.getByText(/142 in · 89 out/)).toBeInTheDocument()
  })

  it("toggles the explanation block when the chevron is clicked", () => {
    render(
      <AIMoment model="GPT-4o" explanation="Two-pass translate then review.">
        <p>x</p>
      </AIMoment>
    )
    expect(
      screen.queryByText("Two-pass translate then review.")
    ).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /how/i }))
    expect(
      screen.getByText("Two-pass translate then review.")
    ).toBeInTheDocument()
  })

  it("does not render the chevron toggle when there is no explanation", () => {
    render(
      <AIMoment model="GPT-4o">
        <p>x</p>
      </AIMoment>
    )
    expect(screen.queryByRole("button", { name: /how/i })).not.toBeInTheDocument()
  })

  it("uses an aria-labelled region for screen readers", () => {
    render(
      <AIMoment model="GPT-4o">
        <p>x</p>
      </AIMoment>
    )
    expect(screen.getByRole("region", { name: /ai-generated content/i })).toBeInTheDocument()
  })
})
