"use client"

import { useEffect } from "react"
import { toast } from "sonner"
import { api } from "@/lib/api"

const STORAGE_KEY = "transmax_active_jobs"

function getActiveJobs(): string[] {
    if (typeof window === "undefined") return []
    try {
        return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]")
    } catch {
        return []
    }
}

function setActiveJobs(jobs: string[]) {
    if (typeof window === "undefined") return
    localStorage.setItem(STORAGE_KEY, JSON.stringify(jobs))
}

export function addActiveJob(docId: string) {
    const jobs = getActiveJobs()
    if (!jobs.includes(docId)) {
        jobs.push(docId)
        setActiveJobs(jobs)
    }
}

export function removeActiveJob(docId: string) {
    const jobs = getActiveJobs().filter(id => id !== docId)
    setActiveJobs(jobs)
}

export function useTranslationNotifications() {
    useEffect(() => {
        const interval = setInterval(async () => {
            const jobs = getActiveJobs()
            if (jobs.length === 0) return

            for (const docId of jobs) {
                try {
                    const doc = await api.documents.get(docId)
                    if (doc.status === "translated" || doc.status === "in_review" || doc.status === "approved") {
                        removeActiveJob(docId)
                        toast.success(`Translation complete: ${doc.name}`, {
                            action: {
                                label: "View",
                                onClick: () => {
                                    window.location.href = `/workspace/documents/${docId}`
                                },
                            },
                            duration: 10000,
                        })
                    } else if (doc.status === "uploaded") {
                        // Failed — reverted to uploaded
                        removeActiveJob(docId)
                        toast.error(`Translation failed: ${doc.name}`)
                    }
                } catch (err: any) {
                    // If 404, document was deleted — stop tracking
                    if (err?.message?.includes("404") || err?.message?.includes("not found")) {
                        removeActiveJob(docId)
                    }
                    // Otherwise keep polling
                }
            }
        }, 10000)

        return () => clearInterval(interval)
    }, [])
}
