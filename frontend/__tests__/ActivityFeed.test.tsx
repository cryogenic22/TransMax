import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import {
  ActivityFeed,
  formatRelativeTime,
  type ActivityEvent,
} from "@/components/ui/ActivityFeed"

const NOW = new Date("2026-05-09T18:00:00Z")

const SAMPLE: ActivityEvent[] = [
  {
    id: "e1",
    actor: { type: "user", id: "carol", name: "Carol (QC)" },
    action: "approved",
    target: "Cardivex SmPC v2.1",
    occurredAt: "2026-05-09T15:00:00Z",
  },
  {
    id: "e2",
    actor: { type: "agent", id: "translator", name: "Translator agent" },
    action: "translated",
    target: "segment 47 of Mounjaro PIL",
    occurredAt: "2026-05-09T17:59:50Z",
  },
  {
    id: "e3",
    actor: { type: "system", id: "drift-detector", name: "Drift detector" },
    action: "flagged",
    target: "glossary term “adverse event” changed upstream",
    occurredAt: "2026-05-08T18:00:00Z",
  },
]

describe("<ActivityFeed>", () => {
  it("renders each event with actor name, action, and target", () => {
    render(<ActivityFeed items={SAMPLE} />)
    expect(screen.getByText("Carol (QC)")).toBeInTheDocument()
    expect(screen.getByText(/approved/)).toBeInTheDocument()
    expect(screen.getByText("Cardivex SmPC v2.1")).toBeInTheDocument()
  })

  it("groups by actor-type with the matching avatar tint class", () => {
    const { container } = render(<ActivityFeed items={SAMPLE} />)
    const userLi = container.querySelector("li[data-actor-type='user']")
    const agentLi = container.querySelector("li[data-actor-type='agent']")
    const systemLi = container.querySelector("li[data-actor-type='system']")
    expect(userLi).toBeInTheDocument()
    expect(agentLi).toBeInTheDocument()
    expect(systemLi).toBeInTheDocument()
  })

  it("renders an empty state when items is empty", () => {
    render(<ActivityFeed items={[]} />)
    expect(screen.getByText(/no recent activity/i)).toBeInTheDocument()
  })

  it("respects the limit prop", () => {
    render(<ActivityFeed items={SAMPLE} limit={1} />)
    const list = screen.getByRole("list")
    expect(list.children.length).toBe(1)
  })
})

describe("formatRelativeTime", () => {
  it("formats seconds", () => {
    expect(formatRelativeTime("2026-05-09T17:59:30Z", NOW)).toBe("30s ago")
  })

  it("formats minutes", () => {
    expect(formatRelativeTime("2026-05-09T17:45:00Z", NOW)).toBe("15m ago")
  })

  it("formats hours", () => {
    expect(formatRelativeTime("2026-05-09T15:00:00Z", NOW)).toBe("3h ago")
  })

  it("formats days", () => {
    expect(formatRelativeTime("2026-05-07T18:00:00Z", NOW)).toBe("2d ago")
  })

  it("formats weeks", () => {
    expect(formatRelativeTime("2026-04-25T18:00:00Z", NOW)).toBe("2w ago")
  })

  it("clamps negative durations to 0s ago", () => {
    expect(formatRelativeTime("2026-05-10T00:00:00Z", NOW)).toBe("0s ago")
  })
})
