"use client"

import { useState, useEffect } from "react"
import TopNavigation from "@/components/TopNavigation"
import Sidebar from "@/components/Sidebar"
import { api } from "@/lib/api"

export default function WorkspaceShell({ children }: { children: React.ReactNode }) {
    const [recentDocuments, setRecentDocuments] = useState<{ id: string; name: string; status: string }[]>([])

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
