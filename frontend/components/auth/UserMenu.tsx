"use client"

import { useState, useRef, useEffect } from "react"
import { useAuth } from "@/lib/auth"
import { ROLE_LABELS, ROLE_COLORS } from "@/lib/permissions"
import { User, ChevronDown, LogOut, Shield } from "lucide-react"

export default function UserMenu() {
  const { user, logout, config } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  if (!user) return null

  const roleLabel = ROLE_LABELS[user.role] || user.role
  const roleColor = ROLE_COLORS[user.role] || "#5f6368"
  const isNoAuth = config?.auth_mode === "none"

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          padding: "0.375rem 0.75rem 0.375rem 0.5rem",
          borderRadius: "24px",
          background: "#f8f9fa",
          border: "none",
          color: "#202124",
          cursor: "pointer",
          fontSize: "0.8125rem",
          fontWeight: 500,
        }}
      >
        <div
          style={{
            width: "28px",
            height: "28px",
            borderRadius: "50%",
            background: `linear-gradient(135deg, ${roleColor}, ${roleColor}dd)`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <User size={14} style={{ color: "white" }} />
        </div>
        {user.name}
        <ChevronDown size={14} style={{ color: "#5f6368" }} />
      </button>

      {open && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            right: 0,
            width: "240px",
            background: "white",
            borderRadius: "12px",
            boxShadow: "0 4px 24px rgba(0,0,0,0.12)",
            border: "1px solid #e8eaed",
            padding: "0.5rem 0",
            zIndex: 200,
          }}
        >
          {/* User info */}
          <div style={{ padding: "0.75rem 1rem", borderBottom: "1px solid #f1f3f4" }}>
            <div style={{ fontSize: "0.875rem", fontWeight: 500, color: "#202124" }}>
              {user.name}
            </div>
            <div style={{ fontSize: "0.75rem", color: "#5f6368", marginTop: "2px" }}>
              {user.email}
            </div>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                marginTop: "6px",
                padding: "2px 8px",
                borderRadius: "12px",
                background: `${roleColor}15`,
                color: roleColor,
                fontSize: "0.6875rem",
                fontWeight: 600,
              }}
            >
              <Shield size={10} />
              {roleLabel}
            </div>
          </div>

          {/* Auth mode indicator (dev) */}
          {isNoAuth && (
            <div
              style={{
                padding: "0.5rem 1rem",
                fontSize: "0.6875rem",
                color: "#9aa0a6",
                borderBottom: "1px solid #f1f3f4",
              }}
            >
              Auth: disabled (dev mode)
            </div>
          )}

          {/* Logout */}
          {!isNoAuth && (
            <button
              onClick={() => {
                logout()
                setOpen(false)
              }}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                width: "100%",
                padding: "0.625rem 1rem",
                background: "none",
                border: "none",
                color: "#d93025",
                fontSize: "0.8125rem",
                cursor: "pointer",
                textAlign: "left",
              }}
            >
              <LogOut size={14} />
              Sign out
            </button>
          )}
        </div>
      )}
    </div>
  )
}
