import { describe, it, expect } from "vitest"
import { cn } from "@/lib/utils"

describe("cn (className helper)", () => {
  it("joins multiple classes", () => {
    expect(cn("a", "b", "c")).toBe("a b c")
  })

  it("filters falsy values", () => {
    expect(cn("a", false, null, undefined, "b")).toBe("a b")
  })

  it("supports conditional classes via clsx semantics", () => {
    expect(cn("base", { active: true, disabled: false })).toBe("base active")
  })

  it("dedupes via tailwind-merge — last wins for conflicting tailwind classes", () => {
    expect(cn("p-2", "p-4")).toBe("p-4")
    expect(cn("text-red-500", "text-green-500")).toBe("text-green-500")
  })

  it("preserves arbitrary non-conflicting classes", () => {
    expect(cn("rounded-full border", "bg-slate-100")).toBe(
      "rounded-full border bg-slate-100"
    )
  })
})
