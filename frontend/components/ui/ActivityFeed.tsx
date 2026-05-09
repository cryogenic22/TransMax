"use client"

import * as React from "react"
import { Bot, User, Cpu, Clock } from "lucide-react"
import { cn } from "@/lib/utils"

export type ActivityActorType = "agent" | "user" | "system"

export interface ActivityEvent {
  id: string
  actor: { type: ActivityActorType; id: string; name: string }
  action: string
  target: string
  occurredAt: string
}

const ACTOR_ICON: Record<ActivityActorType, React.ComponentType<{ size?: number; className?: string }>> = {
  agent: Bot,
  user: User,
  system: Cpu,
}

const ACTOR_TINT: Record<ActivityActorType, string> = {
  agent: "text-violet-600 bg-violet-100 dark:bg-violet-900/30 dark:text-violet-300",
  user: "text-blue-600 bg-blue-100 dark:bg-blue-900/30 dark:text-blue-300",
  system: "text-emerald-600 bg-emerald-100 dark:bg-emerald-900/30 dark:text-emerald-300",
}

/**
 * Format an ISO timestamp as a relative duration. Pure function; testable.
 * 90s ago, 14m ago, 3h ago, 2d ago, 5w ago. Zero deps (no date-fns).
 */
export function formatRelativeTime(iso: string, now: Date = new Date()): string {
  const then = new Date(iso).getTime()
  const diff = Math.max(0, now.getTime() - then)
  const sec = Math.floor(diff / 1000)
  if (sec < 60) return `${sec}s ago`
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h ago`
  const day = Math.floor(hr / 24)
  if (day < 7) return `${day}d ago`
  const week = Math.floor(day / 7)
  return `${week}w ago`
}

export interface ActivityFeedProps extends React.HTMLAttributes<HTMLOListElement> {
  items: ActivityEvent[]
  /** Cap items to render. Default 25. */
  limit?: number
}

/**
 * ActivityFeed — chronological audit-style event stream.
 *
 * Replaces dashboard stat-cards-of-zeros (rescape Direction 2). For an
 * auditable platform the right dashboard hero is the activity log,
 * not "Pending: 0 / Active: 0 / Approved: 0".
 *
 * Backend wiring (TMX-3603-wire) populates `items` from
 * /api/dashboard/activity. This component is presentation-only.
 */
export function ActivityFeed({
  items,
  limit = 25,
  className,
  ...rest
}: ActivityFeedProps) {
  if (items.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-6 text-center text-sm text-muted-foreground">
        <Clock size={20} className="mx-auto mb-2 opacity-40" />
        No recent activity.
      </div>
    )
  }

  const visible = items.slice(0, limit)

  return (
    <ol
      className={cn("divide-y rounded-lg border bg-card", className)}
      aria-label="Recent activity"
      {...rest}
    >
      {visible.map(ev => {
        const Icon = ACTOR_ICON[ev.actor.type]
        return (
          <li
            key={ev.id}
            className="flex items-start gap-3 px-4 py-3"
            data-actor-type={ev.actor.type}
          >
            <div
              className={cn(
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
                ACTOR_TINT[ev.actor.type]
              )}
              aria-hidden
            >
              <Icon size={14} />
            </div>
            <div className="flex-1 min-w-0 text-sm">
              <p className="text-foreground">
                <span className="font-medium">{ev.actor.name}</span>
                <span className="text-muted-foreground"> {ev.action} </span>
                <span className="text-foreground/90">{ev.target}</span>
              </p>
              <time
                dateTime={ev.occurredAt}
                className="text-xs text-muted-foreground"
              >
                {formatRelativeTime(ev.occurredAt)}
              </time>
            </div>
          </li>
        )
      })}
    </ol>
  )
}
