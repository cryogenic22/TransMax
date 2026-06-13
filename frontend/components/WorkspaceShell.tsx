"use client"

import { useState, useEffect } from "react"
import { useRouter, usePathname } from "next/navigation"
import TopNavigation from "@/components/TopNavigation"
import Sidebar from "@/components/Sidebar"
import { api } from "@/lib/api"
import { useAuth } from "@/lib/auth"

export default function WorkspaceShell({ children }: { children: React.ReactNode }) {
    const [recentDocuments, setRecentDocuments] = useState<{ id: string; name: string; status: string }[]>([])

    // TMX-AUTH-WALL: gate the workspace when a login mode is active. In
    // auth_mode=none the dev identity auto-logs-in (isAuthenticated true), so this
    // is a no-op; in jwt/oidc an unauthenticated visitor is redirected to /login
    // BEFORE the workspace renders (no content flash, no reliance on an API 401).
    const { loading, isAuthenticated, config } = useAuth()
    const router = useRouter()
    const pathname = usePathname()
    const authRequired = config?.auth_mode === "jwt" || config?.auth_mode === "oidc"
    const blocked = authRequired && !isAuthenticated

    useEffect(() => {
        if (!loading && blocked) {
            router.replace(`/login?redirect=${encodeURIComponent(pathname)}`)
        }
    }, [loading, blocked, pathname, router])

    useEffect(() => {
        api.documents.list(1, 10).then(docs => {
            setRecentDocuments(
                docs.items.map(doc => ({
                    id: doc.id,
                    name: doc.name || "Untitled",
                    status: doc.status || "uploaded"
                }))
            )
        }).catch(() => {
            // Backend offline - leave empty
        })
    }, [])

    // Refresh recent docs when the route changes (child navigation)
    useEffect(() => {
        const onFocus = () => {
            api.documents.list(1, 10).then(docs => {
                setRecentDocuments(
                    docs.items.map(doc => ({
                        id: doc.id,
                        name: doc.name || "Untitled",
                        status: doc.status || "uploaded"
                    }))
                )
            }).catch(() => {})
        }
        window.addEventListener("focus", onFocus)
        return () => window.removeEventListener("focus", onFocus)
    }, [])

    if (loading || blocked) {
        return (
            <div style={{
                height: "100vh", display: "flex", alignItems: "center",
                justifyContent: "center", background: "#f8f9fa", color: "#5f6368",
                fontFamily: "'Google Sans', 'Outfit', sans-serif",
            }}>
                {blocked ? "Redirecting to sign in…" : "Loading…"}
            </div>
        )
    }

    return (
        <div style={{
            height: "100vh",
            display: "flex",
            flexDirection: "column",
            background: "#f8f9fa",
            overflow: "hidden"
        }}>
            <TopNavigation />
            <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
                <Sidebar recentDocuments={recentDocuments} />
                <main style={{
                    flex: 1,
                    overflow: "auto",
                    position: "relative",
                    display: "flex",
                    flexDirection: "column"
                }}>
                    {children}
                </main>
            </div>
        </div>
    )
}
