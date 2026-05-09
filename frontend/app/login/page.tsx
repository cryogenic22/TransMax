"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { useAuth } from "@/lib/auth"
import { getErrMessage } from "@/lib/utils"
import { Languages, Loader2 } from "lucide-react"

export default function LoginPage() {
  const router = useRouter()
  const { user, config, loading, login, register } = useAuth()
  const [mode, setMode] = useState<"login" | "register">("login")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [name, setName] = useState("")
  const [error, setError] = useState("")
  const [submitting, setSubmitting] = useState(false)

  // If no-auth mode or already logged in, skip to workspace
  useEffect(() => {
    if (!loading && config?.auth_mode === "none") {
      router.replace("/workspace")
    }
    if (!loading && user) {
      router.replace("/workspace")
    }
  }, [loading, config, user, router])

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
        <Loader2 size={32} style={{ animation: "spin 1s linear infinite", color: "#4285f4" }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
      </div>
    )
  }

  // Don't render login form in no-auth mode
  if (config?.auth_mode === "none") return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setSubmitting(true)
    try {
      if (mode === "login") {
        await login(email, password)
      } else {
        await register(email, password, name)
      }
      router.replace("/workspace")
    } catch (err) {
      setError(getErrMessage(err, "Authentication failed"))
    }
    setSubmitting(false)
  }

  const handleSSO = (provider: string) => {
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"
    window.location.href = `${API_BASE}/api/auth/sso/${provider}/authorize`
  }

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "linear-gradient(135deg, #f8f9fa 0%, #e8f0fe 100%)",
      fontFamily: "'Google Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    }}>
      <div style={{
        width: "100%",
        maxWidth: "420px",
        background: "white",
        borderRadius: "16px",
        boxShadow: "0 4px 24px rgba(0,0,0,0.08)",
        padding: "2.5rem",
      }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <div style={{
            width: "48px", height: "48px",
            background: "linear-gradient(135deg, #4285f4, #1a73e8)",
            borderRadius: "14px", display: "inline-flex",
            alignItems: "center", justifyContent: "center",
            boxShadow: "0 2px 12px rgba(66,133,244,0.3)",
          }}>
            <Languages size={24} style={{ color: "white" }} />
          </div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 500, color: "#202124", marginTop: "1rem" }}>
            TransMax
          </h1>
          <p style={{ fontSize: "0.875rem", color: "#5f6368", marginTop: "0.25rem" }}>
            {mode === "login" ? "Sign in to continue" : "Create your account"}
          </p>
        </div>

        {/* SSO Buttons */}
        {config?.sso_providers && config.sso_providers.length > 0 && (
          <>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginBottom: "1.5rem" }}>
              {config.sso_providers.includes("okta") && (
                <button onClick={() => handleSSO("okta")} style={ssoButtonStyle}>
                  Sign in with Okta
                </button>
              )}
              {config.sso_providers.includes("microsoft") && (
                <button onClick={() => handleSSO("microsoft")} style={ssoButtonStyle}>
                  Sign in with Microsoft
                </button>
              )}
              {config.sso_providers.includes("google") && (
                <button onClick={() => handleSSO("google")} style={ssoButtonStyle}>
                  Sign in with Google
                </button>
              )}
            </div>
            <div style={{
              display: "flex", alignItems: "center", gap: "1rem",
              margin: "1.5rem 0", color: "#9aa0a6", fontSize: "0.75rem",
            }}>
              <div style={{ flex: 1, height: "1px", background: "#e8eaed" }} />
              or
              <div style={{ flex: 1, height: "1px", background: "#e8eaed" }} />
            </div>
          </>
        )}

        {/* Email/Password Form */}
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {mode === "register" && (
            <input
              type="text"
              placeholder="Full name"
              value={name}
              onChange={e => setName(e.target.value)}
              required
              style={inputStyle}
            />
          )}
          <input
            type="email"
            placeholder="Email address"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            style={inputStyle}
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            minLength={6}
            style={inputStyle}
          />

          {error && (
            <div style={{
              padding: "0.625rem", borderRadius: "8px",
              background: "#fce8e6", color: "#d93025",
              fontSize: "0.8125rem",
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            style={{
              padding: "0.75rem",
              borderRadius: "8px",
              background: "#1a73e8",
              color: "white",
              border: "none",
              fontSize: "0.875rem",
              fontWeight: 500,
              cursor: submitting ? "not-allowed" : "pointer",
              opacity: submitting ? 0.7 : 1,
            }}
          >
            {submitting ? "Please wait..." : (mode === "login" ? "Sign in" : "Create account")}
          </button>
        </form>

        {/* Toggle login/register */}
        {config?.registration_enabled && (
          <div style={{ textAlign: "center", marginTop: "1.25rem", fontSize: "0.8125rem", color: "#5f6368" }}>
            {mode === "login" ? (
              <>
                No account?{" "}
                <button
                  onClick={() => { setMode("register"); setError("") }}
                  style={{ background: "none", border: "none", color: "#1a73e8", cursor: "pointer", fontWeight: 500 }}
                >
                  Create one
                </button>
              </>
            ) : (
              <>
                Already have an account?{" "}
                <button
                  onClick={() => { setMode("login"); setError("") }}
                  style={{ background: "none", border: "none", color: "#1a73e8", cursor: "pointer", fontWeight: 500 }}
                >
                  Sign in
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  padding: "0.75rem",
  borderRadius: "8px",
  border: "1px solid #dadce0",
  fontSize: "0.875rem",
  outline: "none",
  transition: "border-color 0.15s",
  width: "100%",
  boxSizing: "border-box",
}

const ssoButtonStyle: React.CSSProperties = {
  padding: "0.75rem",
  borderRadius: "8px",
  border: "1px solid #dadce0",
  background: "white",
  fontSize: "0.875rem",
  fontWeight: 500,
  cursor: "pointer",
  color: "#202124",
  transition: "background 0.15s",
}
