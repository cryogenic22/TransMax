import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import { ComplianceView } from "@/components/control_views/ComplianceView"
import type { TrustPosture } from "@/lib/api"

// TMX-POSTURE-FAB (A3): the compliance tab must render ONLY real, backend-derived
// trust posture — never the old fabricated "Zero Retention (Azure OpenAI)" /
// "NER_V2_EN" / "AES-256" / "NO_STORE" cards with live-looking pulse dots.

const mocks = vi.hoisted(() => ({
  getPosture: vi.fn(),
  auditList: vi.fn(),
}))

vi.mock("@/lib/api", () => ({
  api: {
    trust: { getPosture: mocks.getPosture },
    audit: { list: mocks.auditList },
  },
}))

const REAL_POSTURE: TrustPosture = {
  app_env: "test",
  controls: [
    {
      key: "pii_scrubbing",
      label: "PII scrubbing",
      value: "regex-only (C-12)",
      verified: true,
      detail: "Regex-based PII service; Presidio upgrade tracked as TMX-3805.",
    },
    {
      key: "encryption_at_rest",
      label: "Encryption at rest",
      value: "deployment-dependent",
      verified: false,
      detail: "Must be confirmed in the deployment environment.",
    },
  ],
}

beforeEach(() => {
  mocks.getPosture.mockReset()
  mocks.auditList.mockReset()
  mocks.getPosture.mockResolvedValue(REAL_POSTURE)
  mocks.auditList.mockResolvedValue([])
})

describe("<ComplianceView> privacy posture (A3: real posture only)", () => {
  it("never renders the fabricated compliance-claim strings", async () => {
    render(<ComplianceView />)
    // Wait for async settling so we assert against the final DOM.
    await screen.findByText(/no activity recorded/i)

    expect(screen.queryByText(/Zero Retention/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Azure OpenAI/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/NER_V2/)).not.toBeInTheDocument()
    expect(screen.queryByText(/AES-256/)).not.toBeInTheDocument()
    expect(screen.queryByText(/NO_STORE/)).not.toBeInTheDocument()
    expect(screen.queryByText(/US-EAST/)).not.toBeInTheDocument()
  })

  it("fetches and renders the REAL posture from api.trust.getPosture()", async () => {
    render(<ComplianceView />)

    expect(await screen.findByText("PII scrubbing")).toBeInTheDocument()
    expect(mocks.getPosture).toHaveBeenCalledTimes(1)
    expect(screen.getByText("regex-only (C-12)")).toBeInTheDocument()
    // The verified/not-verified honesty distinction must survive the port.
    expect(screen.getByText("Verified")).toBeInTheDocument()
    // "Not verified in-app" also appears in the disclaimer copy; assert the badge itself.
    const notVerified = screen.getAllByText("Not verified in-app")
    expect(notVerified.some((el) => el.className.includes("bg-amber-100"))).toBe(true)
  })

  it("links through to the full Trust Center at /workspace/trust", async () => {
    render(<ComplianceView />)
    await screen.findByText("PII scrubbing")

    const links = screen.getAllByRole("link")
    expect(links.some((a) => a.getAttribute("href") === "/workspace/trust")).toBe(true)
  })

  it("renders an honest error state (no substituted values) when the posture fetch fails", async () => {
    mocks.getPosture.mockRejectedValueOnce(new Error("posture endpoint unreachable"))
    render(<ComplianceView />)

    expect(
      await screen.findByText(/couldn't load trust posture/i)
    ).toBeInTheDocument()
    expect(screen.getByText(/posture endpoint unreachable/)).toBeInTheDocument()
    // A3: failure must not fall back to any claim.
    expect(screen.queryByText(/Zero Retention/i)).not.toBeInTheDocument()
    expect(screen.queryByText("Verified")).not.toBeInTheDocument()
  })

  it("renders an honest empty state when the backend reports zero controls", async () => {
    mocks.getPosture.mockResolvedValueOnce({ app_env: "test", controls: [] })
    render(<ComplianceView />)

    expect(
      await screen.findByText(/no posture controls reported/i)
    ).toBeInTheDocument()
    expect(screen.queryByText(/AES-256/)).not.toBeInTheDocument()
  })
})
