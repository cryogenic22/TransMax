"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useState, useEffect } from "react"
import {
    Languages, Briefcase, BookOpen,
    Upload, LayoutDashboard, Bell,
} from "lucide-react"
import { api } from "@/lib/api"
import UserMenu from "@/components/auth/UserMenu"
import { useTranslationNotifications } from "@/hooks/useTranslationNotifications"

export default function TopNavigation() {
    const pathname = usePathname()
    const [processingCount, setProcessingCount] = useState(0)

    // Feature 3: Background translation notifications
    useTranslationNotifications()

    // Check for processing jobs — back off on failure to avoid spamming
    useEffect(() => {
        let backoff = 10000
        let timeoutId: ReturnType<typeof setTimeout>

        const checkJobs = async () => {
            try {
                const docs = await api.documents.list()
                const processing = docs.items.filter(d => d.status === 'processing').length
                setProcessingCount(processing)
                backoff = 10000 // Reset on success
            } catch {
                backoff = Math.min(backoff * 2, 60000) // Back off up to 60s
            }
            timeoutId = setTimeout(checkJobs, backoff)
        }
        checkJobs()
        return () => clearTimeout(timeoutId)
    }, [])

    const isActive = (path: string) => {
        if (pathname === path) return true
        // For paths with sub-routes, check prefix but avoid false matches
        if (path !== "/workspace" && pathname.startsWith(path + "/")) return true
        // Special case: /workspace/control tabs use query params
        if (path === "/workspace/control" && pathname === "/workspace/control") return true
        return false
    }

    const navItems = [
        { href: "/workspace/upload", label: "Translate", icon: Upload },
        { href: "/workspace/jobs", label: "Jobs", icon: Briefcase, badge: processingCount },
        { href: "/workspace/control", label: "Control Tower", icon: LayoutDashboard },
        { href: "/knowledge", label: "Knowledge", icon: BookOpen },
    ]

    return (
        <header style={{
            height: "64px",
            background: "white",
            borderBottom: "1px solid #e8eaed",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0 1.5rem",
            position: "sticky",
            top: 0,
            zIndex: 100,
            fontFamily: "'Google Sans', 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif"
        }}>
            {/* Logo & Brand */}
            <div style={{ display: "flex", alignItems: "center", gap: "2.5rem" }}>
                <Link href="/workspace" style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.75rem",
                    textDecoration: "none"
                }}>
                    <div style={{
                        width: "36px",
                        height: "36px",
                        background: "linear-gradient(135deg, #4285f4, #1a73e8)",
                        borderRadius: "10px",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        boxShadow: "0 2px 8px rgba(66, 133, 244, 0.25)"
                    }}>
                        <Languages size={20} style={{ color: "white" }} />
                    </div>
                    <span style={{
                        fontSize: "1.25rem",
                        fontWeight: 500,
                        color: "#202124",
                        letterSpacing: "-0.01em"
                    }}>
                        TransMax
                    </span>
                </Link>

                {/* Main Navigation */}
                <nav style={{ display: "flex", gap: "0.25rem" }}>
                    {navItems.map(item => {
                        const Icon = item.icon
                        const active = isActive(item.href)
                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "0.5rem",
                                    padding: "0.5rem 1rem",
                                    borderRadius: "8px",
                                    background: active ? "#e8f0fe" : "transparent",
                                    color: active ? "#1a73e8" : "#5f6368",
                                    textDecoration: "none",
                                    fontSize: "0.875rem",
                                    fontWeight: 500,
                                    transition: "all 0.15s",
                                    position: "relative"
                                }}
                            >
                                <Icon size={16} />
                                {item.label}
                                {item.badge && item.badge > 0 && (
                                    <span style={{
                                        position: "absolute",
                                        top: "4px",
                                        right: "4px",
                                        width: "8px",
                                        height: "8px",
                                        background: "#1a73e8",
                                        borderRadius: "50%",
                                        animation: "pulse 2s infinite"
                                    }} />
                                )}
                            </Link>
                        )
                    })}
                </nav>
            </div>

            {/* Right Side */}
            <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                {/* Pipeline Status */}
                {processingCount > 0 && (
                    <Link href="/workspace/jobs" style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.5rem",
                        padding: "0.375rem 0.75rem",
                        background: "#e8f0fe",
                        borderRadius: "20px",
                        fontSize: "0.75rem",
                        fontWeight: 500,
                        color: "#1a73e8",
                        textDecoration: "none"
                    }}>
                        <div style={{
                            width: "6px",
                            height: "6px",
                            borderRadius: "50%",
                            background: "#1a73e8",
                            animation: "pulse 2s infinite"
                        }} />
                        {processingCount} Processing
                    </Link>
                )}

                {/* Notifications */}
                <button style={{
                    width: "36px",
                    height: "36px",
                    borderRadius: "50%",
                    background: "#f8f9fa",
                    border: "none",
                    color: "#5f6368",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    transition: "background 0.15s"
                }}>
                    <Bell size={18} />
                </button>

                {/* User Menu */}
                <UserMenu />
            </div>

            <style jsx global>{`
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.5; }
                }
            `}</style>
        </header>
    )
}
