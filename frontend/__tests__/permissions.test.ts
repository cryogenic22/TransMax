import { describe, it, expect } from "vitest"
import {
  hasPermission,
  hasRole,
  ROLE_PERMISSIONS,
  ROLE_LABELS,
} from "@/lib/permissions"

describe("permissions — client-side role gating", () => {
  describe("hasPermission", () => {
    it("admin has every permission", () => {
      expect(hasPermission("admin", "system:admin")).toBe(true)
      expect(hasPermission("admin", "users:manage")).toBe(true)
      expect(hasPermission("admin", "document:delete")).toBe(true)
    })

    it("reviewer can approve and reject but not delete", () => {
      expect(hasPermission("reviewer", "review:approve")).toBe(true)
      expect(hasPermission("reviewer", "review:reject")).toBe(true)
      expect(hasPermission("reviewer", "document:delete")).toBe(false)
      expect(hasPermission("reviewer", "users:manage")).toBe(false)
    })

    it("translator cannot approve translations", () => {
      expect(hasPermission("translator", "translate:execute")).toBe(true)
      expect(hasPermission("translator", "review:approve")).toBe(false)
    })

    it("viewer is read-only", () => {
      expect(hasPermission("viewer", "document:read")).toBe(true)
      expect(hasPermission("viewer", "document:create")).toBe(false)
      expect(hasPermission("viewer", "translate:execute")).toBe(false)
    })

    it("returns false for unknown role gracefully", () => {
      // @ts-expect-error - testing the runtime fallback
      expect(hasPermission("nonexistent", "document:read")).toBe(false)
    })
  })

  describe("hasRole", () => {
    it("matches when role is in the allowed list", () => {
      expect(hasRole("admin", ["admin", "project_manager"])).toBe(true)
      expect(hasRole("project_manager", ["admin", "project_manager"])).toBe(
        true
      )
    })

    it("does not match when role is absent", () => {
      expect(hasRole("translator", ["admin", "reviewer"])).toBe(false)
    })
  })

  describe("ROLE_PERMISSIONS shape", () => {
    it("every role has a defined permission set", () => {
      const roles = ["admin", "project_manager", "translator", "reviewer", "curator", "viewer"] as const
      for (const role of roles) {
        expect(ROLE_PERMISSIONS[role]).toBeDefined()
        expect(ROLE_PERMISSIONS[role].size).toBeGreaterThan(0)
      }
    })

    it("ROLE_LABELS covers every role", () => {
      const roles = Object.keys(ROLE_PERMISSIONS) as Array<keyof typeof ROLE_PERMISSIONS>
      for (const role of roles) {
        expect(ROLE_LABELS[role]).toBeTruthy()
      }
    })
  })
})
