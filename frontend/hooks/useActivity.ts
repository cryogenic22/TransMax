"use client"

import { useEffect, useState } from "react"
import type { ActivityEvent } from "@/components/ui/ActivityFeed"
import type { AgentActivity } from "@/components/ui/AgentLanes"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"
const DEFAULT_POLL_MS = 10_000

interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: Error | null
}

/**
 * useActivityFeed — polls /api/dashboard/activity-feed and returns events
 * shaped for the `<ActivityFeed>` component (TMX-3603-wire).
 *
 * Polling rather than SSE for v1 (no streaming infra yet). Default 10s
 * interval; override via the `pollMs` argument.
 */
export function useActivityFeed(
  limit = 25,
  pollMs = DEFAULT_POLL_MS
): AsyncState<ActivityEvent[]> {
  const [state, setState] = useState<AsyncState<ActivityEvent[]>>({
    data: null,
    loading: true,
    error: null,
  })

  useEffect(() => {
    let cancelled = false
    const fetchOnce = async () => {
      try {
        const res = await fetch(
          `${API_BASE}/api/dashboard/activity-feed?limit=${limit}`,
          { credentials: "include" }
        )
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const body = await res.json()
        if (cancelled) return
        setState({
          data: (body.items ?? []) as ActivityEvent[],
          loading: false,
          error: null,
        })
      } catch (err) {
        if (cancelled) return
        setState({
          data: null,
          loading: false,
          error: err instanceof Error ? err : new Error(String(err)),
        })
      }
    }
    fetchOnce()
    const handle = setInterval(fetchOnce, pollMs)
    return () => {
      cancelled = true
      clearInterval(handle)
    }
  }, [limit, pollMs])

  return state
}

/**
 * useAgentActivity — polls /api/dashboard/agent-activity/{auditId} and
 * returns activities shaped for the `<AgentLanes>` component
 * (TMX-3603-wire). Returns empty array (not null) when audit_id is null
 * so consumers can render the empty-state without conditional rendering.
 */
export function useAgentActivity(
  auditId: string | null,
  pollMs = DEFAULT_POLL_MS
): AsyncState<AgentActivity[]> {
  const [state, setState] = useState<AsyncState<AgentActivity[]>>({
    data: null,
    loading: !!auditId,
    error: null,
  })

  useEffect(() => {
    if (!auditId) {
      setState({ data: [], loading: false, error: null })
      return
    }
    let cancelled = false
    const fetchOnce = async () => {
      try {
        const res = await fetch(
          `${API_BASE}/api/dashboard/agent-activity/${encodeURIComponent(auditId)}`,
          { credentials: "include" }
        )
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const body = await res.json()
        if (cancelled) return
        setState({
          data: (body.activities ?? []) as AgentActivity[],
          loading: false,
          error: null,
        })
      } catch (err) {
        if (cancelled) return
        setState({
          data: null,
          loading: false,
          error: err instanceof Error ? err : new Error(String(err)),
        })
      }
    }
    fetchOnce()
    const handle = setInterval(fetchOnce, pollMs)
    return () => {
      cancelled = true
      clearInterval(handle)
    }
  }, [auditId, pollMs])

  return state
}
