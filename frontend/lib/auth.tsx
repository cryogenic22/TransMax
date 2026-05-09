"use client"

import React, { createContext, useContext, useState, useEffect, useCallback } from "react"
import { UserRole, Permission, hasPermission, hasRole as checkRole } from "./permissions"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"

// --- Types ---

export interface AuthUser {
  user_id: string
  email: string
  name: string
  role: UserRole
  auth_provider: string
  is_active: boolean
}

export interface AuthConfig {
  auth_mode: "none" | "jwt" | "oidc"
  sso_providers: string[]
  registration_enabled: boolean
}

interface AuthContextValue {
  user: AuthUser | null
  config: AuthConfig | null
  token: string | null
  loading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name: string) => Promise<void>
  logout: () => void
  hasPermission: (permission: Permission) => boolean
  hasRole: (...roles: UserRole[]) => boolean
}

// --- Cookie helpers (no dependency needed) ---

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null
  const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"))
  return match ? decodeURIComponent(match[2]) : null
}

function setCookie(name: string, value: string, days: number = 7) {
  const expires = new Date(Date.now() + days * 864e5).toUTCString()
  document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Lax`
}

function removeCookie(name: string) {
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
}

// --- Context ---

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [config, setConfig] = useState<AuthConfig | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  // Fetch auth config on mount.
  // TMX-3005 (review F-C01, F-M01): the previous version of this hook
  // injected a hardcoded admin user when the backend was unreachable, and
  // again when /api/auth/login failed in no-auth mode. A reviewer with
  // network failure ended up with admin privileges silently. Both fallbacks
  // are removed; backend unreachability now surfaces as a connectionError
  // state which the UI must show explicitly.
  useEffect(() => {
    fetch(`${API_BASE}/api/auth/config`)
      .then(res => {
        if (!res.ok) {
          throw new Error(`auth/config returned ${res.status}`)
        }
        return res.json()
      })
      .then(cfg => {
        setConfig(cfg)
        if (cfg.auth_mode === "none") {
          // No-auth mode is dev-only; the backend's config endpoint already
          // refuses to advertise auth_mode=none in production (TMX-3003).
          autoLoginNoAuth()
        } else {
          const savedToken = getCookie("transmax_token")
          if (savedToken) {
            validateToken(savedToken)
          } else {
            setLoading(false)
          }
        }
      })
      .catch(() => {
        // Backend unreachable. Do NOT inject a fake admin. Surface an explicit
        // null user with no config; the UI gates on isAuthenticated and will
        // route to /login or show an offline-backend error state.
        setConfig(null)
        setUser(null)
        setToken(null)
        setLoading(false)
      })
  }, [])

  const autoLoginNoAuth = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "admin@transmax.local", password: "" }),
      })
      if (res.ok) {
        const data = await res.json()
        setToken(data.access_token)
        setUser(data.user as AuthUser)
        setCookie("transmax_token", data.access_token)
      }
      // If the login call fails (non-2xx), do nothing — no auto-admin fallback.
    } catch {
      // Network error — do nothing. User stays unauthenticated.
    }
    setLoading(false)
  }

  const validateToken = async (t: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/auth/me`, {
        headers: { Authorization: `Bearer ${t}` },
      })
      if (res.ok) {
        const userData = await res.json()
        setToken(t)
        setUser(userData as AuthUser)
      } else {
        removeCookie("transmax_token")
      }
    } catch {
      removeCookie("transmax_token")
    }
    setLoading(false)
  }

  const login = async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || "Login failed")
    }
    const data = await res.json()
    setToken(data.access_token)
    setUser(data.user as AuthUser)
    setCookie("transmax_token", data.access_token)
    if (data.refresh_token) {
      setCookie("transmax_refresh", data.refresh_token, 7)
    }
  }

  const register = async (email: string, password: string, name: string) => {
    const res = await fetch(`${API_BASE}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || "Registration failed")
    }
    const data = await res.json()
    setToken(data.access_token)
    setUser(data.user as AuthUser)
    setCookie("transmax_token", data.access_token)
  }

  const logout = () => {
    setToken(null)
    setUser(null)
    removeCookie("transmax_token")
    removeCookie("transmax_refresh")
  }

  const checkPermission = useCallback(
    (permission: Permission) => user ? hasPermission(user.role, permission) : false,
    [user]
  )

  const checkUserRole = useCallback(
    (...roles: UserRole[]) => user ? checkRole(user.role, roles) : false,
    [user]
  )

  return (
    <AuthContext.Provider
      value={{
        user,
        config,
        token,
        loading,
        isAuthenticated: !!user,
        login,
        register,
        logout,
        hasPermission: checkPermission,
        hasRole: checkUserRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error("useAuth must be used within <AuthProvider>")
  }
  return ctx
}
